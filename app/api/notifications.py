from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.db.models import User
from app.notifications.service import list_notifications, mark_notification_read

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _serialize(row):
    return {
        "id": row.id,
        "event_type": row.event_type,
        "title": row.title,
        "message": row.message,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "is_read": row.is_read,
        "created_at": row.created_at.isoformat(),
        "read_at": row.read_at.isoformat() if row.read_at else None,
    }


@router.get("")
def notifications(limit: int = Query(50, ge=1, le=200), unread_only: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = list_notifications(db, user.id, limit=limit, unread_only=unread_only)
    return {"notifications": [_serialize(row) for row in rows], "unread_count": sum(not row.is_read for row in rows)}


@router.post("/{notification_id}/read")
def read_notification(notification_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = mark_notification_read(db, user.id, notification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return _serialize(row)
