"""Worker entrypoint: `taskiq worker src.infrastructure.taskiq.worker:broker`.

The worker never imports the API, so it has to pull in the model registry and
the task modules itself: the first so every foreign key can resolve, the
second because importing a task is what registers it on the broker.
"""

from ...modules import registry  # noqa: F401  (registers models on Base.metadata)
from ...modules.ingestion import tasks  # noqa: F401  (registers ingest_document)
from .broker import broker

__all__ = ["broker"]
