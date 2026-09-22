"""Owner/admin notification management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_db
from app.db.models import User
from app.notifications.service import create_notification

router = APIRouter(prefix="/admin/notifications", tags=["admin-notifications"])


class BroadcastNotification(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=5000)
    event_type: str = Field(default="admin.broadcast", min_length=1, max_length=100)
    user_ids: list[str] | None = None


@router.post("/broadcast", status_code=201)
def broadcast(
    payload: BroadcastNotification,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    if payload.user_ids:
        users = db.scalars(select(User).where(User.id.in_(payload.user_ids), User.is_active.is_(True))).all()
    else:
        users = db.scalars(select(User).where(User.is_active.is_(True))).all()
    created = []
    for user in users:
        row = create_notification(
            db, user_id=user.id, event_type=payload.event_type,
            title=payload.title, message=payload.message,
        )
        created.append(row.id)
    db.commit()
    return {"created": len(created), "notification_ids": created}


@router.get("/user/{user_id}")
def user_notifications(
    user_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    from app.notifications.service import list_notifications
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    rows = list_notifications(db, user_id, limit=200)
    return {"notifications": [{
        "id": r.id, "event_type": r.event_type, "title": r.title,
        "message": r.message, "is_read": r.is_read,
        "created_at": r.created_at.isoformat(),
        "read_at": r.read_at.isoformat() if r.read_at else None,
    } for r in rows]}
