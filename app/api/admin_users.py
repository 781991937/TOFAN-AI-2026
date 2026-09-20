"""Owner/admin user and role management API."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_current_user, get_db
from app.auth.models import RoleName, UserRole
from app.db.models import AuditLog, User

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


class RoleChange(BaseModel):
    role: RoleName


class UserStatusChange(BaseModel):
    is_active: bool


def _audit(db: Session, actor_id: str, action: str, resource_id: str, details: dict) -> None:
    db.add(
        AuditLog(
            user_id=actor_id,
            action=action,
            resource_type="user",
            resource_id=resource_id,
            details=json.dumps(details, ensure_ascii=False),
        )
    )


def _actor_is_owner(db: Session, actor_id: str) -> bool:
    return db.scalar(
        select(UserRole.id).where(
            UserRole.user_id == actor_id,
            UserRole.role == RoleName.OWNER,
            UserRole.is_active.is_(True),
        )
    ) is not None


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    result = []
    for user in users:
        roles = db.scalars(
            select(UserRole.role).where(
                UserRole.user_id == user.id,
                UserRole.is_active.is_(True),
            )
        ).all()
        result.append(
            {
                "id": user.id,
                "display_name": user.display_name,
                "email": user.email,
                "phone": user.phone,
                "is_active": user.is_active,
                "created_at": user.created_at,
                "roles": [role.value for role in roles],
            }
        )
    return result


@router.get("/{user_id}/roles")
def list_user_roles(
    user_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    rows = db.scalars(
        select(UserRole).where(UserRole.user_id == user_id)
    ).all()
    return [{"role": row.role.value, "is_active": row.is_active} for row in rows]


@router.post("/{user_id}/roles", status_code=201)
def grant_user_role(
    user_id: str,
    payload: RoleChange,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")

    actor_owner = _actor_is_owner(db, actor.id)
    if payload.role == RoleName.OWNER and not actor_owner:
        raise HTTPException(status_code=403, detail="Only the owner can grant the owner role.")

    existing = db.scalar(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role == payload.role,
        )
    )
    if existing:
        if existing.is_active:
            return {"status": "already_active", "role": payload.role.value}
        existing.is_active = True
    else:
        existing = UserRole(user_id=user_id, role=payload.role, is_active=True)
        db.add(existing)

    _audit(
        db, actor.id, "grant_role", user_id,
        {"role": payload.role.value},
    )
    db.commit()
    return {"status": "granted", "role": payload.role.value}


@router.delete("/{user_id}/roles/{role}", status_code=200)
def revoke_user_role(
    user_id: str,
    role: RoleName,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")

    actor_owner = _actor_is_owner(db, actor.id)
    if role == RoleName.OWNER and not actor_owner:
        raise HTTPException(status_code=403, detail="Only the owner can revoke the owner role.")
    if role == RoleName.OWNER and user_id == actor.id:
        raise HTTPException(status_code=400, detail="The owner cannot revoke their own owner role.")

    row = db.scalar(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role == role,
            UserRole.is_active.is_(True),
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Active role not found.")

    row.is_active = False
    _audit(
        db, actor.id, "revoke_role", user_id,
        {"role": role.value},
    )
    db.commit()
    return {"status": "revoked", "role": role.value}


@router.patch("/{user_id}/status")
def change_user_status(
    user_id: str,
    payload: UserStatusChange,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")

    actor_owner = _actor_is_owner(db, actor.id)
    target_owner = _actor_is_owner(db, user_id)
    if target_owner and not actor_owner:
        raise HTTPException(status_code=403, detail="Only the owner can change owner status.")
    if target_owner and user_id == actor.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="The owner cannot deactivate their own account.")

    target.is_active = payload.is_active
    _audit(
        db, actor.id, "change_user_status", user_id,
        {"is_active": payload.is_active},
    )
    db.commit()
    return {"status": "updated", "is_active": target.is_active}
