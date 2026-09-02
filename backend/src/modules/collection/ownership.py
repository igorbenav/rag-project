"""Scoping reads to the API key that created the collection.

The key is the principal: there are no users, so a collection belongs to
whichever key created it and every other resource inherits that through its
collection. Enforcement lives in the services rather than the handlers so a
new endpoint cannot forget it — a handler that omits the owner does not
compile past mypy, where a handler that omits a check reads fine.

`None` means authentication is disabled, which is how the evaluation harness
and the test suite talk to the service. It scopes to everything, so it must
never be the value reached by a request that failed to authenticate.
"""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Select

from .models import Collection

OwnerId = Optional[UUID]


def owned_by(statement: Select[Any], owner: OwnerId) -> Select[Any]:
    """Restrict a statement that already reaches `Collection` to one owner."""
    if owner is None:
        return statement
    return statement.where(Collection.api_key_id == owner)
