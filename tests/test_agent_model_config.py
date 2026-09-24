"""Tests for data-driven TOFAN agent model/provider configuration."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents import llm
from app.agents.models import Agent, AgentKind, AgentRole, AgentStatus
from app.api.agent_admin import AgentConfigChange, update_agent_config
from app.db.base import Base


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_configured_provider_receives_selected_model(monkeypatch):
    captured = {}

    class FakeProvider:
        provider_name = "openai"
        model_name = "test-model"

    def fake_provider(*, model=None, provider=None):
        captured["model"] = model
        captured["provider"] = provider
        return FakeProvider()

    monkeypatch.setattr(llm, "OpenAIResponsesProvider", fake_provider)

    provider = llm.build_configured_provider(model="future-openai-model", provider="openai")

    assert provider.model_name == "test-model"
    assert captured == {"model": "future-openai-model", "provider": "openai"}


def test_configured_provider_accepts_gemini(monkeypatch):
    captured = {}

    class FakeProvider:
        provider_name = "gemini"
        model_name = "gemini-test"

    def fake_provider(*, model=None, provider=None):
        captured["model"] = model
        captured["provider"] = provider
        return FakeProvider()

    monkeypatch.setattr(llm, "OpenAIResponsesProvider", fake_provider)

    provider = llm.build_configured_provider(model="gemini-test", provider="gemini")

    assert provider.provider_name == "gemini"
    assert captured == {"model": "gemini-test", "provider": "gemini"}


def test_configured_provider_rejects_unknown_provider():
    try:
        llm.build_configured_provider(model="x", provider="unknown")
    except ValueError as exc:
        assert "Unsupported AI provider" in str(exc)
    else:
        raise AssertionError("Unknown provider should be rejected")


def test_owner_config_endpoint_persists_provider_model_and_prompt():
    db = make_db()
    agent = Agent(
        name="TOFAN Tutor",
        slug="tofan-tutor",
        kind=AgentKind.TEACHER,
        role=AgentRole.TEACHER,
        status=AgentStatus.ACTIVE,
        model_provider="openai",
        model_name="old-model",
        system_prompt="old",
    )
    db.add(agent)
    db.commit()

    result = update_agent_config(
        agent.id,
        AgentConfigChange(
            model_provider="gemini",
            model_name="gemini-2.5-flash",
            system_prompt="new instructions",
            memory_enabled=False,
        ),
        db,
        [],
    )

    assert result["model_name"] == "gemini-2.5-flash"
    assert result["model_provider"] == "gemini"
    assert result["memory_enabled"] is False
    assert "gemini" in result["supported_providers"]

    db.refresh(agent)
    assert agent.model_provider == "gemini"
    assert agent.model_name == "gemini-2.5-flash"
    assert agent.system_prompt == "new instructions"
    assert agent.memory_enabled is False
