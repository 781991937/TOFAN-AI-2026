from datetime import datetime

from app.agents.memory import AgentConversation, AgentMessageRecord
from app.agents.memory_service import ConversationMemoryService
from app.agents.providers import AgentMessage, AgentResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-memory"

    def __init__(self, response: str = "Stable preference: concise explanations.") -> None:
        self.response = response
        self.calls = []

    def generate(self, messages, *, system_prompt=None, tools=None):
        self.calls.append((messages, system_prompt, tools))
        return AgentResponse(
            content=self.response,
            provider=self.provider_name,
            model=self.model_name,
        )


def test_memory_service_compacts_and_persists_summary():
    engine = create_engine("sqlite:///:memory:")
    from app.db.base import Base
    from app.agents.models import Agent
    from app.db.models import User

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    agent = Agent(name="Main", slug="tofan-main", kind="orchestrator", status="active")
    user = User(display_name="Test")
    session.add_all([agent, user])
    session.flush()

    conversation = AgentConversation(agent_id=agent.id, user_id=user.id)
    session.add(conversation)
    session.flush()

    for index in range(21):
        session.add(
            AgentMessageRecord(
                conversation_id=conversation.id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"message {index}",
                sequence=index + 1,
                created_at=datetime.utcnow(),
            )
        )
    session.flush()

    provider = FakeProvider()
    service = ConversationMemoryService(provider)
    messages = session.query(AgentMessageRecord).order_by(AgentMessageRecord.sequence).all()

    assert service.compact(session, conversation, messages) is True
    assert conversation.memory_summary == provider.response
    assert conversation.memory_updated_at is not None
    assert provider.calls
