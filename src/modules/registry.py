"""Imports every model so `Base.metadata` is complete before `create_tables()`.

Without this, a table is only registered once something imports its module, so
`create_tables` would silently skip any model whose router is not yet mounted.
"""

from .chunk.models import Chunk
from .collection.models import Collection
from .document.models import Document, DocumentStatus
from .ingestion.models import IngestionJob, IngestionStatus, UploadBlob

__all__ = [
    "Collection",
    "Document",
    "DocumentStatus",
    "Chunk",
    "IngestionJob",
    "IngestionStatus",
    "UploadBlob",
]
