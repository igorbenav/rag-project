"""Contract tests for the ingestion job returned by an upload.

The 202 body is the only representation a client sees before it starts
polling, so it has to carry the same links and ids the later GET does.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

BASE = "/api/v1/collections"
PDF = b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n<< >>\n%%EOF\n"


@pytest_asyncio.fixture
async def collection_id(client: AsyncClient) -> str:
    response = await client.post(BASE, json={"name": "uploads"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture(autouse=True)
def no_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    """The queue is not what these assert, and it needs a live Redis."""

    async def _noop(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr("src.interfaces.api.v1.documents.ingest_document_task.kiq", _noop)


async def _upload(client: AsyncClient, collection_id: str, count: int = 1) -> dict:
    files = [("files", (f"paper-{i}.pdf", PDF, "application/pdf")) for i in range(count)]
    response = await client.post(f"{BASE}/{collection_id}/documents", files=files)
    assert response.status_code == 202, response.text
    return response.json()


class TestAcceptedRepresentation:
    async def test_carries_links(self, client: AsyncClient, collection_id: str) -> None:
        body = await _upload(client, collection_id)

        assert body["_links"]["self"] == f"/api/v1/ingestions/{body['id']}"
        assert body["_links"]["collection"] == f"{BASE}/{collection_id}"
        assert body["_links"]["documents"] == f"{BASE}/{collection_id}/documents"

    async def test_the_self_link_resolves(self, client: AsyncClient, collection_id: str) -> None:
        body = await _upload(client, collection_id)

        assert (await client.get(body["_links"]["self"])).status_code == 200

    async def test_reports_the_documents_it_created(self, client: AsyncClient, collection_id: str) -> None:
        """An empty list here would send a client polling for ids it already has."""
        body = await _upload(client, collection_id, count=3)

        assert len(body["document_ids"]) == 3
        assert body["total_documents"] == 3

    async def test_matches_what_the_later_get_returns(self, client: AsyncClient, collection_id: str) -> None:
        """Two representations of one resource that disagree is the bug worth catching."""
        accepted = await _upload(client, collection_id, count=2)

        fetched = (await client.get(f"/api/v1/ingestions/{accepted['id']}")).json()

        assert accepted["_links"] == fetched["_links"]
        assert sorted(accepted["document_ids"]) == sorted(fetched["document_ids"])
