"""Application-level authentication and authorization rules."""

from collections.abc import Iterable

from .models import RoleName


class AuthorizationError(PermissionError):
    """Raised when a user is not authorized for an operation."""


def has_role(roles: Iterable[RoleName | str], required: RoleName) -> bool:
    """Return whether the supplied role collection contains the required role."""
    return any(str(role) == required.value for role in roles)


def require_role(roles: Iterable[RoleName | str], *required: RoleName) -> None:
    """Require at least one of the supplied roles."""
    if not any(has_role(roles, role) for role in required):
        names = ", ".join(role.value for role in required)
        raise AuthorizationError(f"Required role: {names}")
