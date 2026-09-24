"""Owner/admin controls for TOFAN AI agents."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.bootstrap import MAIN_AGENT_SLUG, ensure_main_agent
from app.agents.llm import SUPPORTED_AI_PROVIDERS
from app.agents.models import Agent, AgentKind, AgentStatus, AgentTool
from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_db

router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])


class AgentStatusChange(BaseModel):
    status: AgentStatus


class AgentToolChange(BaseModel):
    tool_name: str = Field(min_length=1, max_length=150)
    enabled: bool = True


class AgentConfigChange(BaseModel):
    model_provider: str = Field(default="openai", min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=150)
    system_prompt: str | None = Field(default=None, max_length=20000)
    memory_enabled: bool | None = None


@router.post("/main/bootstrap")
def bootstrap_main_agent(db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    agent = ensure_main_agent(db)
    return {"id": agent.id, "name": agent.name, "slug": agent.slug, "kind": agent.kind.value, "status": agent.status.value}


@router.get("")
def list_agents(db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    agents = db.scalars(select(Agent).order_by(Agent.created_at)).all()
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "slug": agent.slug,
            "kind": agent.kind.value,
            "status": agent.status.value,
            "model_provider": agent.model_provider,
            "model_name": agent.model_name,
            "memory_enabled": agent.memory_enabled,
        }
        for agent in agents
    ]


@router.patch("/{agent_id}/status")
def change_agent_status(agent_id: str, payload: AgentStatusChange, db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    if agent.slug == MAIN_AGENT_SLUG and payload.status == AgentStatus.ARCHIVED:
        raise HTTPException(status_code=400, detail="The main orchestrator cannot be archived.")
    agent.status = payload.status
    db.commit()
    db.refresh(agent)
    return {"id": agent.id, "status": agent.status.value}


@router.post("/{agent_id}/tools", status_code=201)
def set_agent_tool(agent_id: str, payload: AgentToolChange, db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    if db.get(Agent, agent_id) is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    row = db.scalar(select(AgentTool).where(AgentTool.agent_id == agent_id, AgentTool.tool_name == payload.tool_name))
    if row is None:
        row = AgentTool(agent_id=agent_id, tool_name=payload.tool_name, enabled=payload.enabled)
        db.add(row)
    else:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return {"agent_id": row.agent_id, "tool_name": row.tool_name, "enabled": row.enabled}


@router.patch("/{agent_id}/config")
def update_agent_config(agent_id: str, payload: AgentConfigChange, db: Session = Depends(get_db), _: list = Depends(require_owner_or_admin)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")

    provider = payload.model_provider.strip().lower()
    if provider not in SUPPORTED_AI_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported AI provider: {provider}. Supported providers: {', '.join(SUPPORTED_AI_PROVIDERS)}.",
        )

    agent.model_provider = provider
    agent.model_name = payload.model_name.strip()
    if payload.system_prompt is not None:
        agent.system_prompt = payload.system_prompt
    if payload.memory_enabled is not None:
        agent.memory_enabled = payload.memory_enabled
    db.commit()
    db.refresh(agent)
    return {
        "id": agent.id,
        "slug": agent.slug,
        "model_provider": agent.model_provider,
        "model_name": agent.model_name,
        "memory_enabled": agent.memory_enabled,
        "supported_providers": list(SUPPORTED_AI_PROVIDERS),
    }
