"""Student-facing conversational endpoint for AI teacher agents."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.llm import build_configured_provider
from app.agents.memory import append_message, build_memory_context, get_or_create_conversation, recent_messages
from app.agents.memory_service import ConversationMemoryService
from app.agents.models import Agent, AgentKind, AgentStatus
from app.agents.orchestrator import MainAgentOrchestrator
from app.agents.providers import AgentMessage
from app.agents.runtime import AgentRuntime, AgentRuntimeError
from app.agents.teaching_policy import TeachingAccessError, consume_response_chars, remaining_response_chars
from app.agents.service import AgentError, AgentService
from app.agents.tools import build_default_registry
from app.auth.dependencies import get_current_user, get_db
from app.db.models import TeachingSource, User


def teacher_tool_guard(db, agent, tool_name, payload):
    if tool_name == "academy.search":
        assigned_native = agent.curriculum_course_id
        requested_native = str(payload.get("curriculum_course_id", "")).strip()
        if assigned_native:
            if not requested_native or requested_native != assigned_native:
                raise RuntimeError("Teacher agent may search only its assigned TOFAN curriculum course.")
            return
        assigned_legacy = agent.teacher_course_id
        requested_legacy = str(payload.get("course_id", "")).strip()
        if not assigned_legacy or requested_legacy != assigned_legacy:
            raise RuntimeError("Legacy teacher agent may search only its assigned course.")

router = APIRouter(prefix="/agent/teacher", tags=["teacher-agent"])
_registry = build_default_registry()
_runtime = AgentRuntime(_registry)
_service = AgentService()
_orchestrator = MainAgentOrchestrator(_runtime, _service, registry=_registry, tool_input_guard=teacher_tool_guard)


class TeacherChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    source: TeachingSource = TeachingSource.STUDENT_FILES


@router.post("/{slug}/chat")
def chat_with_teacher(
    slug: str,
    payload: TeacherChatRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    try:
        agent = _service.get_active(db, slug)
        if agent.kind != AgentKind.TEACHER or agent.status != AgentStatus.ACTIVE:
            raise HTTPException(status_code=404, detail="Active teacher agent not found.")

        # Student entitlement/content gating is deliberately not bypassed here.
        # Until the entitlement service is connected, teacher activation is an
        # administrative gate rather than a claim that all paid content is accessible.
        conversation = get_or_create_conversation(db, agent.id, actor.id)
        previous = recent_messages(db, conversation.id)
        history = [AgentMessage(role=m.role, content=m.content) for m in previous]
        memory_context = build_memory_context(conversation, previous)
        if agent.curriculum_course_id:
            memory_context = (memory_context + "\n\n" if memory_context else "") + "Assigned TOFAN curriculum course ID: " + agent.curriculum_course_id
        elif agent.teacher_course_id:
            memory_context = (memory_context + "\n\n" if memory_context else "") + "Assigned legacy course ID: " + agent.teacher_course_id

        try:
            provider = _orchestrator.provider or build_configured_provider()
            memory_service = ConversationMemoryService(provider)
            structured = memory_service.context_for_agent(db, conversation, agent)
            if structured:
                memory_context = structured + "\n\n" + memory_context
        except RuntimeError:
            pass

        remaining = remaining_response_chars(
            db, user_id=actor.id, agent_id=agent.id,
            source=payload.source,
        )
        if remaining <= 0:
            raise HTTPException(
                status_code=429,
                detail="Daily free response limit of 2000 characters has been reached. Try again after the 24-hour window resets.",
            )

        append_message(db, conversation.id, "user", payload.message)
        result = _orchestrator.run(
            db, agent, actor.id, payload.message,
            history=history, memory_context=memory_context,
        )
        content = result.get("content") or result.get("output") or ""
        if content:
            content = content[:remaining]
            result["content"] = content
            result["output"] = content
            consume_response_chars(
                db, user_id=actor.id, agent_id=agent.id,
                source=__import__("app.db.models", fromlist=["TeachingSource"]).TeachingSource.STUDENT_FILES,
                characters=len(content),
            )
            append_message(db, conversation.id, "assistant", content)

        try:
            provider = _orchestrator.provider or build_configured_provider()
            memory_service = ConversationMemoryService(provider)
            messages = recent_messages(db, conversation.id, limit=1000)
            memory_service.extract_structured_memory(db, conversation, agent, messages)
            memory_service.compact(db, conversation, messages)
        except RuntimeError:
            pass

        db.commit()
        result["conversation_id"] = conversation.id
        return result
    except HTTPException:
        db.rollback()
        raise
    except TeachingAccessError as exc:
        db.rollback()
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except (AgentError, AgentRuntimeError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
