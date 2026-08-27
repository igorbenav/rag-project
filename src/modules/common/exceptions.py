"""Domain errors. The problem-details handlers in `infrastructure.http` map
these onto status codes, so services never raise `HTTPException`.
"""


class DomainError(Exception):
    """Base class for every domain-specific error."""


class ResourceNotFoundError(DomainError):
    """A requested resource does not exist."""


class ResourceExistsError(DomainError):
    """A resource with the same identity already exists."""


class ValidationError(DomainError):
    """Input failed a business rule that Pydantic cannot express."""
