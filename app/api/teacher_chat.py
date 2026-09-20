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
from app.agents.teaching_policy import TeachingAccessError, consume_response_chars, remaining_response_chars, get_or_create_usage
from app.agents.service import AgentError, AgentService
from app.agents.tools import build_default_registry
from app.auth.dependencies import get_current_user, get_db
from app.db.curriculum_models import CurriculumCourse, CurriculumLesson, CurriculumStage, CurriculumUnit, LearningOutcome, CoursePrerequisite
from app.db.identity_models import StudentProfile
from app.db.models import Entitlement, TeachingSource, User
from app.agents.payment_tools import confirm_payment_transaction


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
            course = db.get(CurriculumCourse, agent.curriculum_course_id)
            if course is None or not course.is_active:
                raise HTTPException(status_code=404, detail="TOFAN curriculum course is not available.")
            stage = db.get(CurriculumStage, course.stage_id)
            outcomes = db.scalars(
                __import__("sqlalchemy", fromlist=["select"]).select(LearningOutcome)
                .where(LearningOutcome.course_id == course.id)
                .order_by(LearningOutcome.position)
            ).all()
            units = db.scalars(
                __import__("sqlalchemy", fromlist=["select"]).select(CurriculumUnit)
                .where(CurriculumUnit.course_id == course.id)
                .order_by(CurriculumUnit.position)
            ).all()
            prerequisites = db.scalars(
                __import__("sqlalchemy", fromlist=["select"]).select(CoursePrerequisite)
                .where(CoursePrerequisite.course_id == course.id)
            ).all()
            native_context = (
                f"مقرر TOFAN: {course.code} — {course.name}\n"
                f"المرحلة: {stage.name if stage else 'غير محددة'}\n"
                f"الوحدات: " + ("؛ ".join(x.title for x in units) if units else "لا توجد وحدات مسجلة") + "\n"
                f"مخرجات التعلم: " + ("؛ ".join(x.statement for x in outcomes) if outcomes else "غير محددة") + "\n"
                f"المتطلبات السابقة: {len(prerequisites)} مقرر"
            )
            memory_context = (memory_context + "\n\n" if memory_context else "") + native_context
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

        if payload.source == TeachingSource.GLOBAL_CURRICULUM:
            usage = get_or_create_usage(
                db, user_id=actor.id, agent_id=agent.id,
                source=TeachingSource.GLOBAL_CURRICULUM,
            )
            entitlement = db.scalar(
                __import__("sqlalchemy", fromlist=["select"]).select(Entitlement).where(
                    Entitlement.user_id == actor.id,
                    Entitlement.access_type == TeachingSource.GLOBAL_CURRICULUM.value,
                )
            )
            if not usage.paid_access or entitlement is None:
                raise HTTPException(
                    status_code=403,
                    detail="Global Curriculum access requires confirmed payment by the TOFAN main manager.",
                )

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
                source=payload.source,
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
