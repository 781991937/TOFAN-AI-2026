from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import Notification


def create_notification(db: Session, *, user_id: str, event_type: str, title: str, message: str, resource_type: str | None = None, resource_id: str | None = None) -> Notification:
    row = Notification(user_id=user_id, event_type=event_type, title=title, message=message, resource_type=resource_type, resource_id=resource_id)
    db.add(row)
    db.flush()
    return row


def list_notifications(db: Session, user_id: str, limit: int = 50, unread_only: bool = False) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    return db.scalars(stmt.order_by(desc(Notification.created_at)).limit(limit)).all()


def mark_notification_read(db: Session, user_id: str, notification_id: str) -> Notification | None:
    row = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id))
    if row is None:
        return None
    row.is_read = True
    row.read_at = datetime.utcnow()
    db.commit()
    return row
