"""Persistent and scoped conversation memory for TOFAN AI agents."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base


def new_id() -> str:
    return str(uuid4())


class AgentConversation(Base):
    __tablename__ = "agent_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    memory_summary: Mapped[str | None] = mapped_column(Text)
    memory_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class AgentMemoryItem(Base):
    """Durable memory with an explicit visibility scope.

    USER memory is shareable only through AgentMemoryPermission.
    CONVERSATION memory is restricted to its conversation agent.
    AGENT_PRIVATE memory is restricted to owner_agent_id.
    SYSTEM memory is never exposed by generic memory context unless explicitly granted.
    """

    __tablename__ = "agent_memory_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("agent_conversations.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    owner_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"))
    memory_scope: Mapped[str] = mapped_column(String(30), nullable=False, default="conversation")
    memory_type: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    source_message_sequence: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class AgentMemoryPermission(Base):
    """Explicit per-agent access to shareable USER/SYSTEM memory."""

    __tablename__ = "agent_memory_permissions"
    __table_args__ = (
        UniqueConstraint("memory_item_id", "agent_id", name="uq_agent_memory_permission"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    memory_item_id: Mapped[str] = mapped_column(ForeignKey("agent_memory_items.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    can_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


def get_or_create_conversation(db: Session, agent_id: str, user_id: str) -> AgentConversation:
    conversation = (
        db.query(AgentConversation)
        .filter(AgentConversation.agent_id == agent_id, AgentConversation.user_id == user_id)
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
    last = db.query(AgentMessageRecord).filter(
        AgentMessageRecord.conversation_id == conversation_id
    ).order_by(AgentMessageRecord.sequence.desc()).first()
    record = AgentMessageRecord(
        conversation_id=conversation_id, role=role, content=content,
        sequence=(last.sequence + 1 if last else 1),
    )
    db.add(record)
    return record


def recent_messages(db: Session, conversation_id: str, limit: int = 12) -> list[AgentMessageRecord]:
    rows = db.query(AgentMessageRecord).filter(
        AgentMessageRecord.conversation_id == conversation_id
    ).order_by(AgentMessageRecord.sequence.desc()).limit(limit).all()
    return list(reversed(rows))


def build_memory_context(conversation: AgentConversation, messages: list[AgentMessageRecord]) -> str:
    parts = []
    if conversation.memory_summary:
        parts.append("Persistent conversation memory:\n" + conversation.memory_summary)
    if messages:
        parts.append(
            "Recent conversation:\n" +
            "\n".join(f"{m.role}: {m.content}" for m in messages)
        )
    return "\n\n".join(parts)


def update_memory_summary(db: Session, conversation: AgentConversation, summary: str) -> None:
    conversation.memory_summary = summary.strip()
    conversation.memory_updated_at = datetime.utcnow()
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)


def memory_readable_by(db: Session, item: AgentMemoryItem, agent_id: str) -> bool:
    if not item.active:
        return False
    if item.memory_scope == "conversation":
        return item.owner_agent_id == agent_id
    if item.memory_scope == "agent_private":
        return item.owner_agent_id == agent_id
    permission = db.query(AgentMemoryPermission).filter(
        AgentMemoryPermission.memory_item_id == item.id,
        AgentMemoryPermission.agent_id == agent_id,
        AgentMemoryPermission.can_read.is_(True),
    ).first()
    return permission is not None


def memory_writable_by(db: Session, item: AgentMemoryItem, agent_id: str) -> bool:
    if not item.active:
        return False
    if item.memory_scope in {"conversation", "agent_private"}:
        return item.owner_agent_id == agent_id
    permission = db.query(AgentMemoryPermission).filter(
        AgentMemoryPermission.memory_item_id == item.id,
        AgentMemoryPermission.agent_id == agent_id,
        AgentMemoryPermission.can_write.is_(True),
    ).first()
    return permission is not None


def memory_deletable_by(db: Session, item: AgentMemoryItem, agent_id: str) -> bool:
    if not item.active:
        return False
    if item.memory_scope in {"conversation", "agent_private"}:
        return item.owner_agent_id == agent_id
    permission = db.query(AgentMemoryPermission).filter(
        AgentMemoryPermission.memory_item_id == item.id,
        AgentMemoryPermission.agent_id == agent_id,
        AgentMemoryPermission.can_delete.is_(True),
    ).first()
    return permission is not None


def active_memory_items(
    db: Session,
    conversation_id: str,
    agent_id: str,
    limit: int = 30,
) -> list[AgentMemoryItem]:
    items = db.query(AgentMemoryItem).filter(
        AgentMemoryItem.conversation_id == conversation_id,
        AgentMemoryItem.active.is_(True),
    ).order_by(AgentMemoryItem.updated_at.desc()).limit(limit * 2).all()
    return [item for item in items if memory_readable_by(db, item, agent_id)][:limit]


def upsert_memory_item(
    db: Session,
    conversation_id: str,
    user_id: str,
    agent_id: str,
    memory_type: str,
    content: str,
    confidence: float = 1.0,
    source_message_sequence: int | None = None,
    memory_scope: str = "user",
) -> AgentMemoryItem:
    if memory_scope not in {"user", "conversation", "agent_private", "system"}:
        raise ValueError("Unsupported memory scope.")
    normalized = content.strip()
    existing = db.query(AgentMemoryItem).filter(
        AgentMemoryItem.conversation_id == conversation_id,
        AgentMemoryItem.memory_type == memory_type,
        AgentMemoryItem.content == normalized,
        AgentMemoryItem.memory_scope == memory_scope,
        AgentMemoryItem.active.is_(True),
    ).first()
    now = datetime.utcnow()
    if existing:
        if not memory_writable_by(db, existing, agent_id):
            raise PermissionError("Agent is not allowed to update this memory.")
        existing.confidence = max(existing.confidence, min(confidence, 1.0))
        existing.updated_at = now
        if source_message_sequence is not None:
            existing.source_message_sequence = source_message_sequence
        db.add(existing)
        return existing

    item = AgentMemoryItem(
        conversation_id=conversation_id,
        user_id=user_id,
        owner_agent_id=agent_id,
        memory_scope=memory_scope,
        memory_type=memory_type,
        content=normalized,
        confidence=min(max(confidence, 0.0), 1.0),
        source_message_sequence=source_message_sequence,
    )
    db.add(item)
    db.flush()

    # The creating agent gets explicit access to shareable memory.
    if memory_scope in {"user", "system"}:
        db.add(AgentMemoryPermission(
            memory_item_id=item.id,
            agent_id=agent_id,
            can_read=True,
            can_write=True,
            can_delete=True,
        ))
    return item


def deactivate_memory_item(db: Session, item_id: str, user_id: str, actor_agent_id: str | None = None) -> bool:
    item = db.query(AgentMemoryItem).filter(
        AgentMemoryItem.id == item_id,
        AgentMemoryItem.user_id == user_id,
        AgentMemoryItem.active.is_(True),
    ).first()
    if not item:
        return False
    if actor_agent_id and not memory_deletable_by(db, item, actor_agent_id):
        return False
    item.active = False
    item.updated_at = datetime.utcnow()
    db.add(item)
    return True


def update_memory_item(
    db: Session,
    item_id: str,
    user_id: str,
    content: str,
    confidence: float | None = None,
    actor_agent_id: str | None = None,
) -> AgentMemoryItem | None:
    item = db.query(AgentMemoryItem).filter(
        AgentMemoryItem.id == item_id,
        AgentMemoryItem.user_id == user_id,
        AgentMemoryItem.active.is_(True),
    ).first()
    if not item:
        return None
    if actor_agent_id and not memory_writable_by(db, item, actor_agent_id):
        return None
    item.content = content.strip()
    if confidence is not None:
        item.confidence = min(max(confidence, 0.0), 1.0)
    item.updated_at = datetime.utcnow()
    db.add(item)
    return item
