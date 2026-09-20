"""Protected conversational entry point for the TOFAN Main Agent."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.memory import append_message, build_memory_context, get_or_create_conversation, recent_messages
from app.agents.memory_service import ConversationMemoryService
from app.agents.llm import build_configured_provider
from app.agents.orchestrator import MainAgentOrchestrator
from app.agents.providers import AgentMessage
from app.agents.runtime import AgentRuntime, AgentRuntimeError
from app.agents.service import AgentError, AgentService
from app.agents.tools import build_default_registry
from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_current_user, get_db
from app.db.models import User

router = APIRouter(prefix="/admin/agent", tags=["admin-agent"])
_registry = build_default_registry()
_runtime = AgentRuntime(_registry)
_service = AgentService()
_orchestrator = MainAgentOrchestrator(_runtime, _service, registry=_registry)


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)


@router.post("/tofan-main/chat")
def chat_with_main_agent(payload: AgentChatRequest, db: Session = Depends(get_db),
                         actor: User = Depends(get_current_user), _: list = Depends(require_owner_or_admin)):
    try:
        agent = _service.get_active(db, "tofan-main")
        conversation = get_or_create_conversation(db, agent.id, actor.id)
        previous = recent_messages(db, conversation.id)
        history = [AgentMessage(role=m.role, content=m.content) for m in previous]
        memory_context = build_memory_context(conversation, previous)
        append_message(db, conversation.id, "user", payload.message)
        result = _orchestrator.run(
            db, agent, actor.id, payload.message,
            history=history, memory_context=memory_context,
        )
        assistant_content = result.get("content") or result.get("output") or ""
        if assistant_content:
            append_message(db, conversation.id, "assistant", assistant_content)
        db.commit()
        result["conversation_id"] = conversation.id
        return result
    except (AgentError, AgentRuntimeError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
