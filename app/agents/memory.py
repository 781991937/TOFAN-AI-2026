"""Persistent conversation memory for the TOFAN Main Agent."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.db.base import Base


def new_id() -> str:
    return str(uuid4())


class AgentConversation(Base):
    __tablename__ = "agent_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class AgentMessageRecord(Base):
    __tablename__ = "agent_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("agent_conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


def get_or_create_conversation(db: Session, agent_id: str, user_id: str) -> AgentConversation:
    conversation = (
        db.query(AgentConversation)
        .filter(
            AgentConversation.agent_id == agent_id,
            AgentConversation.user_id == user_id,
        )
        .order_by(AgentConversation.updated_at.desc())
        .first()
    )
    if conversation:
        return conversation
    conversation = AgentConversation(agent_id=agent_id, user_id=user_id)
    db.add(conversation)
    db.flush()
    return conversation


def append_message(db: Session, conversation_id: str, role: str, content: str) -> AgentMessageRecord:
    last = (
        db.query(AgentMessageRecord)
        .filter(AgentMessageRecord.conversation_id == conversation_id)
        .order_by(AgentMessageRecord.sequence.desc())
        .first()
    )
    record = AgentMessageRecord(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sequence=(last.sequence + 1 if last else 1),
    )
    db.add(record)
    return record


def recent_messages(db: Session, conversation_id: str, limit: int = 20) -> list[AgentMessageRecord]:
    rows = (
        db.query(AgentMessageRecord)
        .filter(AgentMessageRecord.conversation_id == conversation_id)
        .order_by(AgentMessageRecord.sequence.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))
