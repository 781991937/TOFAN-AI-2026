"""Tests for scoped agent memory boundaries."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.memory import (
    AgentMemoryPermission,
    AgentMemoryItem,
    memory_readable_by,
    upsert_memory_item,
)
from app.agents.models import Agent
from app.db.base import Base
from app.db.models import User


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed(db):
    user = User(display_name="Student", email="student@example.com")
    db.add(user)
    db.flush()
    main = Agent(name="Main", slug="main-test", kind="orchestrator")
    teacher = Agent(name="Teacher", slug="teacher-test", kind="teacher")
    db.add_all([main, teacher])
    db.flush()
    return user, main, teacher


def test_user_memory_is_not_visible_without_permission():
    db = make_db()
    user, main, teacher = seed(db)
    conversation = __import__("app.agents.memory", fromlist=["AgentConversation"]).AgentConversation(
        agent_id=main.id, user_id=user.id
    )
    db.add(conversation)
    db.flush()

    item = upsert_memory_item(
        db, conversation.id, user.id, main.id, "goal",
        "Build TOFAN", 0.95, 1, memory_scope="user"
    )
    db.flush()

    assert memory_readable_by(db, item, main.id)
    assert not memory_readable_by(db, item, teacher.id)

    db.add(AgentMemoryPermission(
        memory_item_id=item.id, agent_id=teacher.id,
        can_read=True, can_write=False, can_delete=False
    ))
    db.flush()
    assert memory_readable_by(db, item, teacher.id)


def test_conversation_memory_is_agent_private():
    db = make_db()
    user, main, teacher = seed(db)
    from app.agents.memory import AgentConversation
    conversation = AgentConversation(agent_id=main.id, user_id=user.id)
    db.add(conversation)
    db.flush()
    item = upsert_memory_item(
        db, conversation.id, user.id, main.id, "task",
        "Private task", 0.95, 1, memory_scope="conversation"
    )
    assert memory_readable_by(db, item, main.id)
    assert not memory_readable_by(db, item, teacher.id)
