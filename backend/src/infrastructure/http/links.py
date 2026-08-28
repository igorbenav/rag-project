"""Hypermedia links attached to every representation.

A response that carries a chunk id makes the client construct
`/api/v1/chunks/{id}`; a response that carries the URL does not. That is the
difference between a client that knows the URL scheme and one that only knows
how to follow a link, and it is what lets the scheme change without breaking
every consumer.

Links are a flat `{rel: href}` map rather than HAL's nested
`{rel: {"href": …}}`. The nesting exists to hang templating and metadata off
each link; nothing here needs either, and the flat form is one less unwrapping
step for every client.
"""

from typing import Dict
from uuid import UUID

from .constants import API_PREFIX


def collection_links(collection_id: UUID) -> Dict[str, str]:
    """Where to go from a collection."""
    base = f"{API_PREFIX}/collections/{collection_id}"
    return {"self": base, "documents": f"{base}/documents", "queries": f"{base}/queries"}


def document_links(document_id: UUID, collection_id: UUID) -> Dict[str, str]:
    """Where to go from a document."""
    return {
        "self": f"{API_PREFIX}/documents/{document_id}",
        "chunks": f"{API_PREFIX}/documents/{document_id}/chunks",
        "collection": f"{API_PREFIX}/collections/{collection_id}",
    }


def chunk_links(chunk_id: UUID, document_id: UUID) -> Dict[str, str]:
    """Where to go from a chunk. This is what a citation resolves to."""
    return {
        "self": f"{API_PREFIX}/chunks/{chunk_id}",
        "document": f"{API_PREFIX}/documents/{document_id}",
    }


def ingestion_links(job_id: UUID, collection_id: UUID) -> Dict[str, str]:
    """Where to go from an ingestion job."""
    return {
        "self": f"{API_PREFIX}/ingestions/{job_id}",
        "collection": f"{API_PREFIX}/collections/{collection_id}",
        "documents": f"{API_PREFIX}/collections/{collection_id}/documents",
    }


def query_links(query_id: UUID, collection_id: UUID) -> Dict[str, str]:
    """Where to go from a stored query."""
    return {
        "self": f"{API_PREFIX}/queries/{query_id}",
        "collection": f"{API_PREFIX}/collections/{collection_id}",
    }
