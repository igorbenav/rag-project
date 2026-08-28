"""Application settings, grouped by concern and composed into one Settings class."""

import logging
import os
from enum import Enum
from typing import List

from pydantic_settings import BaseSettings
from starlette.config import Config

logger = logging.getLogger(__name__)

current_file_dir = os.path.dirname(os.path.realpath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, "..", "..", ".."))

env_paths = ["/code/.env", os.path.join(project_root, ".env")]
env_path = next((path for path in env_paths if os.path.isfile(path)), env_paths[-1])

config = Config(env_path)


class EnvironmentOption(str, Enum):
    """Deployment environment, which drives logging and docs visibility."""

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    LOCAL = "local"


class EnvironmentSettings(BaseSettings):
    ENVIRONMENT: EnvironmentOption = config("ENVIRONMENT", default=EnvironmentOption.DEVELOPMENT, cast=EnvironmentOption)


class DatabaseSettings(BaseSettings):
    POSTGRES_USER: str = config("POSTGRES_USER", default="postgres")
    POSTGRES_PASSWORD: str = config("POSTGRES_PASSWORD", default="postgres")
    POSTGRES_SERVER: str = config("POSTGRES_SERVER", default="localhost")
    POSTGRES_PORT: int = config("POSTGRES_PORT", default=5432, cast=int)
    POSTGRES_DB: str = config("POSTGRES_DB", default="ragdb")
    POSTGRES_ASYNC_PREFIX: str = config("POSTGRES_ASYNC_PREFIX", default="postgresql+asyncpg://")

    POSTGRES_POOL_SIZE: int = config("POSTGRES_POOL_SIZE", default=20, cast=int)
    POSTGRES_MAX_OVERFLOW: int = config("POSTGRES_MAX_OVERFLOW", default=0, cast=int)

    CREATE_TABLES_ON_STARTUP: bool = config("CREATE_TABLES_ON_STARTUP", default=True, cast=bool)

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"{self.POSTGRES_ASYNC_PREFIX}{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:"
            f"{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


class CORSSettings(BaseSettings):
    CORS_ENABLED: bool = config("CORS_ENABLED", default=True, cast=bool)
    CORS_ORIGINS: str = config("CORS_ORIGINS", default="*")
    CORS_ALLOW_CREDENTIALS: bool = config("CORS_ALLOW_CREDENTIALS", default=True, cast=bool)
    CORS_ALLOW_METHODS: str = config("CORS_ALLOW_METHODS", default="*")
    CORS_ALLOW_HEADERS: str = config("CORS_ALLOW_HEADERS", default="*")

    @property
    def CORS_ORIGINS_LIST(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return ["*"]
        return [x.strip() for x in self.CORS_ORIGINS.split(",") if x.strip()]


class APISettings(BaseSettings):
    API_PREFIX: str = "/api/v1"
    ENABLE_DOCS_IN_PRODUCTION: bool = config("ENABLE_DOCS_IN_PRODUCTION", default=False, cast=bool)
    GZIP_ENABLED: bool = config("GZIP_ENABLED", default=True, cast=bool)
    GZIP_MINIMUM_SIZE: int = config("GZIP_MINIMUM_SIZE", default=1000, cast=int)


class AppSettings(BaseSettings):
    APP_NAME: str = "RAG over PDFs"
    APP_DESCRIPTION: str = "Retrieval-augmented generation over PDF knowledge bases"
    VERSION: str = "0.1.0"
    DEBUG: bool = config("DEBUG", default=False, cast=bool)


class MistralSettings(BaseSettings):
    MISTRAL_API_KEY: str = config("MISTRAL_API_KEY", default="")
    MISTRAL_EMBED_MODEL: str = config("MISTRAL_EMBED_MODEL", default="mistral-embed")
    # Intent, transformation and reranking: short prompts, decisions a small
    # model makes correctly and cheaply.
    MISTRAL_CHAT_MODEL: str = config("MISTRAL_CHAT_MODEL", default="mistral-small-latest")

    # Generation reads several passages at once and must notice when the one it
    # wants is absent. Measured on the evaluation questions, mistral-small got
    # 3/5 — answering "12" from a BERT passage when asked about the Transformer,
    # and answering a GPT-4 question from a Transformer passage. mistral-medium
    # got 5/5 at the same latency.
    MISTRAL_GENERATION_MODEL: str = config("MISTRAL_GENERATION_MODEL", default="mistral-medium-latest")

    # mistral-embed returns 1024 dimensions. Every index is built to this, so
    # changing it invalidates stored embeddings.
    EMBEDDING_DIM: int = config("EMBEDDING_DIM", default=1024, cast=int)

    # Texts per embeddings request. Mistral caps request size, not batch count,
    # so this is a throughput knob rather than a hard API limit.
    EMBEDDING_BATCH_SIZE: int = config("EMBEDDING_BATCH_SIZE", default=64, cast=int)

    MISTRAL_TIMEOUT_MS: int = config("MISTRAL_TIMEOUT_MS", default=60000, cast=int)
    MISTRAL_MAX_RETRY_ELAPSED_MS: int = config("MISTRAL_MAX_RETRY_ELAPSED_MS", default=30000, cast=int)


class RetrievalSettings(BaseSettings):
    RETRIEVAL_CANDIDATES: int = config("RETRIEVAL_CANDIDATES", default=20, cast=int)
    RETRIEVAL_TOP_K: int = config("RETRIEVAL_TOP_K", default=5, cast=int)
    RETRIEVAL_RRF_K: int = config("RETRIEVAL_RRF_K", default=60, cast=int)

    # Fused candidates shown to the reranker. Every one costs prompt tokens and
    # latency, and the fused list is already ordered, so reranking a long tail
    # of poor candidates buys little.
    RERANK_CANDIDATES: int = config("RERANK_CANDIDATES", default=20, cast=int)

    # Calibrated in Phase 7 against the evaluation set. Zero until then, so
    # nothing is silently refused on an unmeasured threshold.
    RETRIEVAL_MIN_SIMILARITY: float = config("RETRIEVAL_MIN_SIMILARITY", default=0.0, cast=float)


class TaskiqSettings(BaseSettings):
    TASKIQ_REDIS_URL: str = config("TASKIQ_REDIS_URL", default="redis://redis:6379/0")
    TASKIQ_QUEUE_NAME: str = config("TASKIQ_QUEUE_NAME", default="ingestion")

    # Retries per task. Ingestion is idempotent per document — a retry rewrites
    # the same chunks — so retrying a transient Mistral failure is safe.
    TASKIQ_MAX_RETRIES: int = config("TASKIQ_MAX_RETRIES", default=2, cast=int)

    # Milliseconds an unacknowledged task may sit with a stalled worker before
    # another reclaims it. Kept low because reclaiming is cheap: ingesting a
    # document replaces its chunks, so a task run twice costs duplicated work
    # rather than duplicated data. One minute is ~12x the slowest sample PDF.
    TASKIQ_IDLE_TIMEOUT_MS: int = config("TASKIQ_IDLE_TIMEOUT_MS", default=60000, cast=int)


class LoggingSettings(BaseSettings):
    LOG_LEVEL: str = config("LOG_LEVEL", default="INFO")
    # "text" or "json". json is one object per line, for log collectors.
    LOG_FORMAT: str = config("LOG_FORMAT", default="text")

    LOG_CONSOLE_ENABLED: bool = config("LOG_CONSOLE_ENABLED", default=True, cast=bool)
    LOG_FILE_ENABLED: bool = config("LOG_FILE_ENABLED", default=False, cast=bool)
    LOG_FILE_PATH: str = config("LOG_FILE_PATH", default="logs/rag.log")
    LOG_FILE_MAX_SIZE: int = config("LOG_FILE_MAX_SIZE", default=10485760, cast=int)
    LOG_FILE_BACKUP_COUNT: int = config("LOG_FILE_BACKUP_COUNT", default=5, cast=int)

    LOG_SQL_QUERIES: bool = config("LOG_SQL_QUERIES", default=False, cast=bool)

    @property
    def LOG_LEVEL_INT(self) -> int:
        return getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)


class Settings(
    EnvironmentSettings,
    DatabaseSettings,
    CORSSettings,
    APISettings,
    AppSettings,
    MistralSettings,
    RetrievalSettings,
    TaskiqSettings,
    LoggingSettings,
):
    """Every setting the application reads, in one object."""


settings = Settings()


def get_settings() -> Settings:
    """Return the application settings singleton."""
    return settings
