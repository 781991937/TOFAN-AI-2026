"""Owner/admin-only academy administration API."""

from fastapi import APIRouter, Depends

from app.auth.authorization import require_owner_or_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status")
def admin_status(roles=Depends(require_owner_or_admin)):
    return {
        "admin_access": True,
        "roles": [role.value for role in roles],
    }
