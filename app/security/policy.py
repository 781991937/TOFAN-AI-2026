"""Security policy for sensitive academy operations."""

from app.auth.models import RoleName
from app.auth.service import require_role


def require_content_management(roles: list[RoleName | str]) -> None:
    require_role(
        roles,
        RoleName.OWNER,
        RoleName.ADMIN,
        RoleName.INSTRUCTOR,
        RoleName.CONTRIBUTOR,
        RoleName.REVIEWER,
    )


def require_financial_approval(roles: list[RoleName | str]) -> None:
    # Financial approval is deliberately restricted to trusted operators.
    require_role(roles, RoleName.OWNER, RoleName.ADMIN)


def require_platform_administration(roles: list[RoleName | str]) -> None:
    require_role(roles, RoleName.OWNER, RoleName.ADMIN)
