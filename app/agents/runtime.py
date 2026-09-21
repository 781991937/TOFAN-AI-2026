"""Safe runtime for executing explicitly enabled agent tools."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Agent, AgentRun, AgentStatus, AgentTool
from .tools import ToolExecutionError, ToolRegistry
from .models import AgentRole
from .workforce_policy import SPECIALIST_TOOL_ALLOWLIST


class AgentRuntimeError(RuntimeError):
    """Base error for agent runtime failures."""


class AgentRuntime:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute_tool(
        self,
        db: Session,
        agent: Agent,
        tool_name: str,
        input_text: str,
        actor_user_id: str | None = None,
    ) -> AgentRun:
        if agent.status != AgentStatus.ACTIVE:
            raise AgentRuntimeError("Agent is not active.")

        enabled = db.scalar(
            select(AgentTool.id).where(
                AgentTool.agent_id == agent.id,
                AgentTool.tool_name == tool_name,
                AgentTool.enabled.is_(True),
            )
        )
        if enabled is None:
            raise AgentRuntimeError("Tool is not enabled for this agent.")

        tool = self.registry.get(tool_name)
        if tool.allowed_agent_slug and agent.slug != tool.allowed_agent_slug:
            raise AgentRuntimeError("This tool is restricted to its authorized agent.")
        # Defense in depth: database AgentTool rows cannot expand a specialist's
        # role beyond the canonical workforce policy.
        if agent.role not in {AgentRole.GENERAL_MANAGER, AgentRole.TEACHER}:
            allowed = SPECIALIST_TOOL_ALLOWLIST.get(agent.role, ())
            if tool_name not in allowed:
                raise AgentRuntimeError("Tool is outside this specialist's role policy.")
        run = AgentRun(
            agent_id=agent.id,
            actor_user_id=actor_user_id,
            tool_name=tool_name,
            status="running",
            input_text=input_text,
        )
        db.add(run)
        db.flush()

        try:
            output = tool.handler(db, input_text)
            run.status = "completed"
            run.output_text = output
            run.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(run)
            return run
        except ToolExecutionError:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise ToolExecutionError("Tool execution failed.") from exc
