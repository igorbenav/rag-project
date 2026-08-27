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
        created = await _create(client)

        response = await client.patch(f"{BASE}/{created['id']}", json={"name": "renamed"})

        assert response.status_code == 405
        assert response.headers["content-type"] == PROBLEM
        assert response.json()["type"] == "/problems/method-not-allowed"


class TestCascade:
    async def test_deleting_a_collection_removes_its_documents_and_chunks(self, client: AsyncClient, db: AsyncSession) -> None:
        created = await _create(client)
        collection_id = UUID(created["id"])

        document = Document(collection_id=collection_id, filename="report.pdf", checksum="a" * 64)
        db.add(document)
        await db.commit()
        db.add(Chunk(document_id=document.id, content="text", page=1, ordinal=0, embedding=[0.1, 0.2]))
        await db.commit()

        counts = (await client.get(f"{BASE}/{collection_id}")).json()
        assert (counts["document_count"], counts["chunk_count"]) == (1, 1)

        assert (await client.delete(f"{BASE}/{collection_id}")).status_code == 204

        assert await db.scalar(select(func.count()).select_from(Document)) == 0
        assert await db.scalar(select(func.count()).select_from(Chunk)) == 0
