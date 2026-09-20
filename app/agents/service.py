"""Core agent registry and safe tool execution contracts."""

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Agent, AgentStatus, AgentTool


class AgentError(RuntimeError):
    """Base error for agent operations."""


class AgentToolExecutor(Protocol):
    def execute(self, tool_name: str, input_text: str) -> str:
        """Execute one explicitly registered tool."""


@dataclass(frozen=True)
class AgentContext:
    agent: Agent
    actor_user_id: str | None


class AgentService:
    def get_active(self, db: Session, slug: str) -> Agent:
        agent = db.scalar(
            select(Agent).where(
                Agent.slug == slug,
                Agent.status == AgentStatus.ACTIVE,
            )
        )
        if agent is None:
            raise AgentError("Active agent not found.")
        return agent

    def list_enabled_tools(self, db: Session, agent_id: str) -> list[str]:
        rows = db.scalars(
            select(AgentTool).where(
                AgentTool.agent_id == agent_id,
                AgentTool.enabled.is_(True),
            )
        ).all()
        return [row.tool_name for row in rows]
