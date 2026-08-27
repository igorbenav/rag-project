"""Create database tables from the SQLAlchemy models.

Useful when running the app with CREATE_TABLES_ON_STARTUP=false, and as the
setup step for anything that needs a schema without booting the API.
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database.session import create_tables  # noqa: E402

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Creating database tables...")

    try:
        await create_tables()
    except Exception:
        logger.exception("Failed to create database tables")
        sys.exit(1)

    logger.info("Database tables created.")


if __name__ == "__main__":
    asyncio.run(main())
