"""FastAPI dependencies for role-protected endpoints."""

from fastapi import Depends, HTTPException

from app.auth.dependencies import get_current_roles
from app.auth.models import RoleName
from app.auth.service import has_role


def require_any_role(*required: RoleName):
    def dependency(roles=Depends(get_current_roles)):
        if not any(has_role(roles, role) for role in required):
            raise HTTPException(status_code=403, detail="Insufficient permissions.")
        return roles

    dependency.dependency = dependency
    return dependency


require_owner_or_admin = require_any_role(RoleName.OWNER, RoleName.ADMIN)
