"""Authorisation: one key must never reach another key's data.

Authentication is covered elsewhere — these start from a request that already
presented a valid key and check what it is allowed to see. The flat resources
matter most: `/chunks/{id}` and friends carry no collection in the path, so
each has to resolve ownership by joining back up, and a missed join there is
an IDOR that no happy-path test would notice.

Every miss is a 404 rather than a 403, so the API never confirms that another
key's id exists.
"""

from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.config.settings import get_settings
from src.infrastructure.http.problem import ProblemException
from src.interfaces.api.dependencies import get_owner_id
from src.interfaces.main import app
from src.modules.api_key.models import APIKey
from src.modules.chunk.models import Chunk
from src.modules.collection.models import Collection
from src.modules.document.models import Document, DocumentStatus
from src.modules.ingestion.models import IngestionJob, IngestionStatus
from src.modules.query.models import Query

BASE = "/api/v1"


@pytest_asyncio.fixture
async def keys(db: AsyncSession) -> AsyncGenerator[dict, None]:
    """Two real key rows: collections carry a foreign key to them."""
    alice = APIKey(name="alice", lookup_hash="a" * 64, secret_hash="x")
    bob = APIKey(name="bob", lookup_hash="b" * 64, secret_hash="y")
    db.add_all([alice, bob])
    await db.commit()
    yield {"alice": alice.id, "bob": bob.id}


@pytest.fixture
def as_key():
    """Present the request as a chosen key."""

    def _use(owner: UUID) -> None:
        app.dependency_overrides[get_owner_id] = lambda: owner

    yield _use
    app.dependency_overrides.pop(get_owner_id, None)


@pytest_asyncio.fixture
async def alices(db: AsyncSession, keys: dict) -> AsyncGenerator[dict, None]:
    """A full resource tree owned by Alice, written straight to the database."""
    collection = Collection(name="alice's papers", api_key_id=keys["alice"])
    db.add(collection)
    await db.flush()

    job = IngestionJob(collection_id=collection.id, status=IngestionStatus.COMPLETED, total_documents=1)
    db.add(job)
    await db.flush()

    document = Document(
        collection_id=collection.id,
        filename="secret.pdf",
        checksum="a" * 64,
        ingestion_job_id=job.id,
        status=DocumentStatus.READY,
        page_count=1,
    )
    db.add(document)
    await db.flush()

    chunk = Chunk(
        document_id=document.id,
        content="confidential",
        page=1,
        ordinal=0,
        embedding=[0.1] * 8,
        embedding_model="test",
    )
    query = Query(collection_id=collection.id, question="what?", answer="this")
    db.add_all([chunk, query])
    await db.commit()

    yield {
        "collection": collection.id,
        "job": job.id,
        "document": document.id,
        "chunk": chunk.id,
        "query": query.id,
    }


class TestBobCannotReachAlicesData:
    """Every read path, from Bob's authenticated but unrelated key."""

    @pytest.mark.parametrize(
        "path",
        [
            "/collections/{collection}",
            "/collections/{collection}/documents",
            "/collections/{collection}/queries",
            "/documents/{document}",
            "/documents/{document}/chunks",
            "/chunks/{chunk}",
            "/ingestions/{job}",
            "/queries/{query}",
        ],
    )
    async def test_get_is_not_found(self, client: AsyncClient, as_key, keys: dict, alices: dict, path: str) -> None:
        as_key(keys["bob"])

        response = await client.get(BASE + path.format(**alices))

        assert response.status_code == 404, f"{path} leaked: {response.text}"

    async def test_cannot_delete_the_collection(self, client: AsyncClient, as_key, keys: dict, alices: dict) -> None:
        as_key(keys["bob"])

        assert (await client.delete(f"{BASE}/collections/{alices['collection']}")).status_code == 404

    async def test_cannot_delete_the_document(self, client: AsyncClient, as_key, keys: dict, alices: dict) -> None:
        as_key(keys["bob"])

        assert (await client.delete(f"{BASE}/documents/{alices['document']}")).status_code == 404

    async def test_cannot_rename_the_collection(self, client: AsyncClient, as_key, keys: dict, alices: dict) -> None:
        as_key(keys["bob"])

        response = await client.patch(f"{BASE}/collections/{alices['collection']}", json={"name": "mine now"})

        assert response.status_code == 404

    async def test_cannot_upload_into_it(self, client: AsyncClient, as_key, keys: dict, alices: dict) -> None:
        as_key(keys["bob"])

        response = await client.post(
            f"{BASE}/collections/{alices['collection']}/documents",
            files=[("files", ("x.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf"))],
        )

        assert response.status_code == 404

    async def test_cannot_query_it(self, client: AsyncClient, as_key, keys: dict, alices: dict) -> None:
        """The expensive one: a leak here would also spend Alice's corpus on Bob's question."""
        as_key(keys["bob"])

        response = await client.post(f"{BASE}/collections/{alices['collection']}/queries", json={"question": "what?"})

        assert response.status_code == 404

    async def test_listing_does_not_include_it(self, client: AsyncClient, as_key, keys: dict, alices: dict) -> None:
        as_key(keys["bob"])

        body = (await client.get(f"{BASE}/collections")).json()

        assert body["total"] == 0
        assert body["items"] == []


class TestAliceStillReachesHerOwn:
    """The scoping has to let the owner through, or it is just an outage."""

    @pytest.mark.parametrize(
        "path",
        [
            "/collections/{collection}",
            "/collections/{collection}/documents",
            "/collections/{collection}/queries",
            "/documents/{document}",
            "/documents/{document}/chunks",
            "/chunks/{chunk}",
            "/ingestions/{job}",
            "/queries/{query}",
        ],
    )
    async def test_get_succeeds(self, client: AsyncClient, as_key, keys: dict, alices: dict, path: str) -> None:
        as_key(keys["alice"])

        assert (await client.get(BASE + path.format(**alices))).status_code == 200

    async def test_listing_includes_it(self, client: AsyncClient, as_key, keys: dict, alices: dict) -> None:
        as_key(keys["alice"])

        body = (await client.get(f"{BASE}/collections")).json()

        assert body["total"] == 1
        assert body["items"][0]["id"] == str(alices["collection"])


class TestOwnershipIsRecordedOnCreate:
    async def test_a_new_collection_belongs_to_the_creating_key(
        self, client: AsyncClient, as_key, keys: dict, db: AsyncSession
    ) -> None:
        as_key(keys["alice"])

        created = (await client.post(f"{BASE}/collections", json={"name": "mine"})).json()

        stored = await db.get(Collection, UUID(created["id"]))
        assert stored is not None
        assert stored.api_key_id == keys["alice"]


class TestUnscopedAccessFailsClosed:
    """`None` owner means "see everything", so it must be unreachable when auth is on.

    The guard exists for a mistake that hasn't been made: a router registered
    without the `require_api_key` dependency. That would serve every key's data
    with a completely ordinary-looking 200.
    """

    def _request(self, authenticated: bool) -> Request:
        scope = {"type": "http", "headers": [], "method": "GET", "path": "/"}
        request = Request(scope)
        if authenticated:
            request.state.api_key_id = uuid4()
        return request

    def test_refuses_when_auth_is_required_but_never_ran(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(get_settings(), "API_KEY_REQUIRED", True)

        with pytest.raises(ProblemException) as raised:
            get_owner_id(self._request(authenticated=False))

        assert raised.value.status_code == 401

    def test_allows_the_unscoped_case_when_auth_is_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The evaluation harness and this suite both rely on it."""
        monkeypatch.setattr(get_settings(), "API_KEY_REQUIRED", False)

        assert get_owner_id(self._request(authenticated=False)) is None

    def test_passes_the_key_through_when_authenticated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(get_settings(), "API_KEY_REQUIRED", True)
        request = self._request(authenticated=True)

        assert get_owner_id(request) == request.state.api_key_id
