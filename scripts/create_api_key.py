"""Mint an API key.

    docker compose exec web python scripts/create_api_key.py "my client"

The key is printed once and cannot be recovered afterwards; only its hashes
are stored.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database.session import local_session  # noqa: E402
from src.modules import registry  # noqa: E402,F401  (registers models)
from src.modules.api_key.service import APIKeyService  # noqa: E402


async def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "default"

    async with local_session() as db:
        record, key = await APIKeyService().create(name, db)

    print(f"\n  name : {record.name}")
    print(f"  id   : {record.id}")
    print(f"  key  : {key}")
    print("\n  Store it now. It is not recoverable.\n")


if __name__ == "__main__":
    asyncio.run(main())
