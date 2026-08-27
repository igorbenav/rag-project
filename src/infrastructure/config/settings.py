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


class LoggingSettings(BaseSettings):
    LOG_LEVEL: str = config("LOG_LEVEL", default="INFO")
    LOG_FORMAT: str = config("LOG_FORMAT", default="structured")

    LOG_CONSOLE_ENABLED: bool = config("LOG_CONSOLE_ENABLED", default=True, cast=bool)
    LOG_FILE_ENABLED: bool = config("LOG_FILE_ENABLED", default=False, cast=bool)
    LOG_FILE_PATH: str = config("LOG_FILE_PATH", default="logs/rag.log")
    LOG_FILE_MAX_SIZE: int = config("LOG_FILE_MAX_SIZE", default=10485760, cast=int)
    LOG_FILE_BACKUP_COUNT: int = config("LOG_FILE_BACKUP_COUNT", default=5, cast=int)

    LOG_CORRELATION_ID: bool = config("LOG_CORRELATION_ID", default=True, cast=bool)
    LOG_STRUCTURED_CONTEXT: bool = config("LOG_STRUCTURED_CONTEXT", default=True, cast=bool)
    LOG_PERFORMANCE_METRICS: bool = config("LOG_PERFORMANCE_METRICS", default=False, cast=bool)
    LOG_LOGFIRE_INTEGRATION: bool = config("LOG_LOGFIRE_INTEGRATION", default=False, cast=bool)
    LOG_SQL_QUERIES: bool = config("LOG_SQL_QUERIES", default=False, cast=bool)
    LOG_INCLUDE_STACKTRACE: bool = config("LOG_INCLUDE_STACKTRACE", default=True, cast=bool)
    LOG_DEVELOPMENT_VERBOSE: bool = config("LOG_DEVELOPMENT_VERBOSE", default=True, cast=bool)
    LOG_PRODUCTION_OPTIMIZE: bool = config("LOG_PRODUCTION_OPTIMIZE", default=True, cast=bool)

    @property
    def LOG_LEVEL_INT(self) -> int:
        return getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)


class Settings(
    EnvironmentSettings,
    DatabaseSettings,
    CORSSettings,
    APISettings,
    AppSettings,
    LoggingSettings,
):
    """Every setting the application reads, in one object."""


settings = Settings()


def get_settings() -> Settings:
    """Return the application settings singleton."""
    return settings
