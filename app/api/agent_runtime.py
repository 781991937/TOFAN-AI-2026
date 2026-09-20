"""Protected runtime endpoint for the TOFAN Main Agent tool layer."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.runtime import AgentRuntime, AgentRuntimeError
from app.agents.service import AgentService
from app.agents.tools import build_default_registry
from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_current_user, get_db
from app.db.models import User

router = APIRouter(prefix="/admin/agent-runtime", tags=["admin-agent-runtime"])

_registry = build_default_registry()
_runtime = AgentRuntime(_registry)
_service = AgentService()


class ToolExecutionRequest(BaseModel):
    tool_name: str = Field(min_length=1, max_length=150)
    input_text: str = Field(default="", max_length=10000)


@router.get("/tools")
def list_registered_tools(
    _: list = Depends(require_owner_or_admin),
):
    return [
        {"name": name, "description": _registry.get(name).description}
        for name in _registry.names()
    ]


@router.post("/{agent_slug}/execute")
def execute_tool(
    agent_slug: str,
    payload: ToolExecutionRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: list = Depends(require_owner_or_admin),
):
    try:
        agent = _service.get_active(db, agent_slug)
        run = _runtime.execute_tool(
            db,
            agent,
            payload.tool_name,
            payload.input_text,
            actor_user_id=actor.id,
        )
    except (AgentRuntimeError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "run_id": run.id,
        "agent_id": run.agent_id,
        "tool_name": run.tool_name,
        "status": run.status,
        "output": run.output_text,
    }
