"""Ingestion tasks. Registered on the broker; executed by the worker process."""

from uuid import UUID

from taskiq import TaskiqEvents, TaskiqState

from ...infrastructure.config.settings import get_settings
from ...infrastructure.logging import get_logger
from ...infrastructure.taskiq import broker
from .service import find_unfinished_documents, ingest_document, mark_job_finished

logger = get_logger(__name__)
settings = get_settings()


@broker.task(
    task_name="ingestion.ingest_document",
    retry_on_error=True,
    max_retries=settings.TASKIQ_MAX_RETRIES,
)
async def ingest_document_task(document_id: str, job_id: str) -> None:
    """Ingest one document, then close the job if it was the last one.

    Takes identifiers rather than bytes: task arguments cross a process
    boundary through Redis, and the file is already durable in the database.
    """
    await ingest_document(UUID(document_id))
    await mark_job_finished(UUID(job_id))


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def requeue_unfinished(state: TaskiqState) -> None:
    """Re-enqueue work interrupted by a worker that died.

    The broker reclaims unacknowledged messages, but only while draining new
    ones — an idle queue never reaches that path, so a crash on the last task
    of a batch would strand it until the next upload. Re-enqueuing from the
    database instead makes recovery independent of broker internals.

    Safe to run repeatedly: ingesting a document replaces its chunks, so a
    document already in flight elsewhere is redone, not corrupted.
    """
    unfinished = await find_unfinished_documents()
    if not unfinished:
        return

    logger.info("Re-enqueueing %d interrupted document(s)", len(unfinished))
    for document_id, job_id in unfinished:
        await ingest_document_task.kiq(str(document_id), str(job_id))
