"""Contract tests for the collections resource.

These assert status codes, headers and media types — the parts of the contract
a client actually couples to. Bodies are checked only where the contract
promises a specific field.
"""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.chunk.models import Chunk
from src.modules.document.models import Document

PROBLEM = "application/problem+json"
BASE = "/api/v1/collections"


async def _create(client: AsyncClient, name: str = "filings") -> dict:
    response = await client.post(BASE, json={"name": name})
    assert response.status_code == 201
    return response.json()


class TestCreate:
    async def test_returns_201_with_location_pointing_at_the_new_collection(self, client: AsyncClient) -> None:
        response = await client.post(BASE, json={"name": "10-K filings", "metadata": {"year": 2025}})

        assert response.status_code == 201
        body = response.json()
        assert response.headers["location"] == f"{BASE}/{body['id']}"

        follow = await client.get(response.headers["location"])
        assert follow.status_code == 200
        assert follow.json()["id"] == body["id"]

    async def test_identifier_is_a_uuid_not_a_sequence(self, client: AsyncClient) -> None:
        first = UUID((await _create(client, "one"))["id"])
        second = UUID((await _create(client, "two"))["id"])
        assert first != second

    async def test_rejects_empty_name_as_problem_json(self, client: AsyncClient) -> None:
        response = await client.post(BASE, json={"name": ""})

        assert response.status_code == 422
        assert response.headers["content-type"] == PROBLEM
        body = response.json()
        assert body["type"] == "/problems/validation-failed"
        assert body["status"] == 422
        assert body["instance"] == BASE
        assert any(error["field"] == "body.name" for error in body["errors"])


class TestList:
    async def test_envelope_reports_the_unpaginated_total(self, client: AsyncClient) -> None:
        for index in range(5):
            await _create(client, f"collection-{index}")

        response = await client.get(BASE, params={"limit": 2})

        assert response.status_code == 200
        body = response.json()
        assert [body["total"], body["limit"], body["offset"], len(body["items"])] == [5, 2, 0, 2]

    async def test_link_header_omits_prev_on_the_first_page(self, client: AsyncClient) -> None:
        for index in range(5):
            await _create(client, f"collection-{index}")

        link = (await client.get(BASE, params={"limit": 2})).headers["link"]

        assert 'rel="next"' in link
        assert 'rel="first"' in link
        assert 'rel="prev"' not in link

    async def test_link_header_omits_next_on_the_last_page(self, client: AsyncClient) -> None:
        for index in range(5):
            await _create(client, f"collection-{index}")

        link = (await client.get(BASE, params={"limit": 2, "offset": 4})).headers["link"]

        assert 'rel="prev"' in link
        assert 'rel="next"' not in link

    async def test_link_header_preserves_unrelated_query_parameters(self, client: AsyncClient) -> None:
        await _create(client)

        link = (await client.get(BASE, params={"limit": 1, "unrelated": "kept"})).headers["link"]

        assert "unrelated=kept" in link

    @pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 500}, {"offset": -1}])
    async def test_rejects_out_of_range_pagination(self, client: AsyncClient, params: dict) -> None:
        response = await client.get(BASE, params=params)

        assert response.status_code == 422
        assert response.headers["content-type"] == PROBLEM


class TestRead:
    async def test_counts_start_at_zero(self, client: AsyncClient) -> None:
        created = await _create(client)

        body = (await client.get(f"{BASE}/{created['id']}")).json()

        assert body["document_count"] == 0
        assert body["chunk_count"] == 0

    async def test_unknown_id_is_404_problem_json(self, client: AsyncClient) -> None:
        response = await client.get(f"{BASE}/{uuid4()}")

        assert response.status_code == 404
        assert response.headers["content-type"] == PROBLEM
        assert response.json()["type"] == "/problems/not-found"

    async def test_malformed_id_is_422_naming_the_path_parameter(self, client: AsyncClient) -> None:
        response = await client.get(f"{BASE}/not-a-uuid")

        assert response.status_code == 422
        assert response.headers["content-type"] == PROBLEM
        assert response.json()["errors"][0]["field"] == "path.collection_id"


class TestDelete:
    async def test_returns_204_with_no_body(self, client: AsyncClient) -> None:
        created = await _create(client)

        response = await client.delete(f"{BASE}/{created['id']}")

        assert response.status_code == 204
        assert response.content == b""

    async def test_is_404_once_already_deleted(self, client: AsyncClient) -> None:
        created = await _create(client)
        await client.delete(f"{BASE}/{created['id']}")

        response = await client.delete(f"{BASE}/{created['id']}")

        assert response.status_code == 404
        assert response.headers["content-type"] == PROBLEM


class TestMethodHandling:
    async def test_unsupported_method_is_405_problem_json(self, client: AsyncClient) -> None:
        """PUT is not offered: an update here is partial, so PATCH is the verb."""
        created = await _create(client)

        response = await client.put(f"{BASE}/{created['id']}", json={"name": "renamed"})

        assert response.status_code == 405
        assert response.headers["content-type"] == PROBLEM
        assert response.json()["type"] == "/problems/method-not-allowed"


class TestPartialUpdate:
    async def test_patch_changes_only_what_it_names(self, client: AsyncClient) -> None:
        created = await client.post(BASE, json={"name": "original", "description": "keep me"})
        collection = created.json()

        response = await client.patch(f"{BASE}/{collection['id']}", json={"name": "renamed"})

        assert response.status_code == 200
        assert response.json()["name"] == "renamed"
        assert response.json()["description"] == "keep me"

    async def test_patch_of_a_missing_collection_is_404(self, client: AsyncClient) -> None:
        response = await client.patch(f"{BASE}/{uuid4()}", json={"name": "x"})

        assert response.status_code == 404
        assert response.headers["content-type"] == PROBLEM


class TestConditionalRequests:
    async def test_a_read_carries_an_etag(self, client: AsyncClient) -> None:
        created = await _create(client)

        response = await client.get(f"{BASE}/{created['id']}")

        assert response.headers.get("etag")

    async def test_returning_the_etag_gets_304_and_no_body(self, client: AsyncClient) -> None:
        created = await _create(client)
        etag = (await client.get(f"{BASE}/{created['id']}")).headers["etag"]

        response = await client.get(f"{BASE}/{created['id']}", headers={"If-None-Match": etag})

        assert response.status_code == 304
        assert response.content == b""
        assert response.headers["etag"] == etag

    async def test_a_stale_etag_gets_the_body(self, client: AsyncClient) -> None:
        created = await _create(client)

        response = await client.get(f"{BASE}/{created['id']}", headers={"If-None-Match": '"stale"'})

        assert response.status_code == 200

    async def test_a_write_with_a_stale_if_match_is_rejected(self, client: AsyncClient) -> None:
        """The lost-update case: two clients read, both write, one silently loses."""
        created = await _create(client)
        etag = (await client.get(f"{BASE}/{created['id']}")).headers["etag"]
        await client.patch(f"{BASE}/{created['id']}", json={"description": "first writer"})

        response = await client.patch(
            f"{BASE}/{created['id']}", json={"description": "second writer"}, headers={"If-Match": etag}
        )

        assert response.status_code == 412
        assert response.json()["type"] == "/problems/precondition-failed"

    async def test_the_rejected_write_did_not_apply(self, client: AsyncClient) -> None:
        created = await _create(client)
        etag = (await client.get(f"{BASE}/{created['id']}")).headers["etag"]
        await client.patch(f"{BASE}/{created['id']}", json={"description": "first writer"})

        await client.patch(f"{BASE}/{created['id']}", json={"description": "second writer"}, headers={"If-Match": etag})

        current = (await client.get(f"{BASE}/{created['id']}")).json()
        assert current["description"] == "first writer"

    async def test_a_delete_with_a_stale_if_match_leaves_it_alone(self, client: AsyncClient) -> None:
        created = await _create(client)
        etag = (await client.get(f"{BASE}/{created['id']}")).headers["etag"]
        await client.patch(f"{BASE}/{created['id']}", json={"description": "changed"})

        response = await client.delete(f"{BASE}/{created['id']}", headers={"If-Match": etag})

        assert response.status_code == 412
        assert (await client.get(f"{BASE}/{created['id']}")).status_code == 200

    async def test_if_match_is_optional(self, client: AsyncClient) -> None:
        """Requiring it would break every client that does not send one."""
        created = await _create(client)

        assert (await client.delete(f"{BASE}/{created['id']}")).status_code == 204


class TestHypermedia:
    async def test_every_representation_carries_links(self, client: AsyncClient) -> None:
        created = await _create(client)

        body = (await client.get(f"{BASE}/{created['id']}")).json()

        assert body["_links"]["self"] == f"{BASE}/{created['id']}"
        assert body["_links"]["documents"].endswith("/documents")
        assert body["_links"]["queries"].endswith("/queries")

    async def test_the_self_link_resolves(self, client: AsyncClient) -> None:
        created = await _create(client)
        body = (await client.get(f"{BASE}/{created['id']}")).json()

        assert (await client.get(body["_links"]["self"])).status_code == 200


class TestCascade:
    async def test_deleting_a_collection_removes_its_documents_and_chunks(self, client: AsyncClient, db: AsyncSession) -> None:
        created = await _create(client)
        collection_id = UUID(created["id"])

        document = Document(collection_id=collection_id, filename="report.pdf", checksum="a" * 64)
        db.add(document)
        await db.commit()
        db.add(
            Chunk(
                document_id=document.id,
                content="text",
                page=1,
                ordinal=0,
                embedding=[0.1, 0.2],
                embedding_model="test-embed",
            )
        )
        await db.commit()

        counts = (await client.get(f"{BASE}/{collection_id}")).json()
        assert (counts["document_count"], counts["chunk_count"]) == (1, 1)

        assert (await client.delete(f"{BASE}/{collection_id}")).status_code == 204

        assert await db.scalar(select(func.count()).select_from(Document)) == 0
        assert await db.scalar(select(func.count()).select_from(Chunk)) == 0
