"""Creating and authenticating API keys."""

from datetime import UTC, datetime
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.logging import get_logger
from .models import APIKey
from .utils import generate_key, lookup_hash, secret_hash, verify

logger = get_logger(__name__)


class APIKeyService:
    """Issues keys and checks the ones presented."""

    async def create(self, name: str, db: AsyncSession) -> Tuple[APIKey, str]:
        """Create a key. The plaintext is returned here and never again."""
        key = generate_key()
        record = APIKey(name=name, lookup_hash=lookup_hash(key), secret_hash=secret_hash(key))

        db.add(record)
        await db.commit()
        return record, key

    async def authenticate(self, key: str, db: AsyncSession) -> Optional[APIKey]:
        """Return the key's record, or None if it is unknown or revoked.

        Looks up by the fast hash, then verifies with bcrypt. A presented key
        that matches no row still costs one indexed query and no bcrypt work,
        which is the point of storing both.
        """
        record = (await db.execute(select(APIKey).where(APIKey.lookup_hash == lookup_hash(key)))).scalar_one_or_none()

        if record is None or not record.is_active:
            return None

        if not verify(key, record.secret_hash):
            logger.warning("API key %s failed verification despite a lookup match", record.id)
            return None

        record.last_used_at = datetime.now(UTC)
        await db.commit()
        return record

    async def count(self, db: AsyncSession) -> int:
        return len((await db.execute(select(APIKey.id))).all())
