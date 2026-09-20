"""Tool registry for the TOFAN agent runtime."""

import json
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.curriculum_models import CurriculumCourse, CurriculumLesson, CurriculumUnit
from app.db.models import AcademicUnit, Course, Institution, Lecture, Unit
from .payment_tools import confirm_payment_tool
from .main_manager import MainManagerService
from .models import AgentStatus


class ToolExecutionError(RuntimeError):
    """Raised when a registered tool cannot be executed."""


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    handler: Callable[[Session, str], str]
    sensitive: bool = False
    parameters: dict | None = None
    allowed_agent_slug: str | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolExecutionError("Unknown tool.")
        return tool

    def names(self) -> list[str]:
        return sorted(self._tools)

    def openai_definitions(self, names: list[str] | None = None) -> list[dict]:
        selected = names if names is not None else self.names()
        definitions = []
        for name in selected:
            tool = self.get(name)
            definitions.append(
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                    or {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                    "strict": True,
                }
            )
        return definitions


def echo_tool(_: Session, input_text: str) -> str:
    return input_text


def health_tool(_: Session, _: str) -> str:
    return "ok"


def academy_structure_tool(db: Session, _: str) -> str:
    institutions = db.scalars(
        select(Institution).where(Institution.is_active.is_(True)).order_by(Institution.name)
    ).all()
    result = []
    for institution in institutions:
        units = db.scalars(
            select(AcademicUnit)
            .where(AcademicUnit.institution_id == institution.id, AcademicUnit.is_active.is_(True))
            .order_by(AcademicUnit.name)
        ).all()
        result.append(
            {
                "institution": {
                    "id": institution.id,
                    "name": institution.name,
                    "code": institution.code,
                },
                "units": [
                    {
                        "id": unit.id,
                        "parent_id": unit.parent_id,
                        "name": unit.name,
                        "unit_type": unit.unit_type,
                    }
                    for unit in units
                ],
            }
        )
    return json.dumps({"institutions": result}, ensure_ascii=False)


def academy_search_tool(db: Session, input_text: str) -> str:
    try:
        payload = json.loads(input_text or "{}")
    except json.JSONDecodeError as exc:
        raise ToolExecutionError("Input must be valid JSON.") from exc

    query = str(payload.get("query", "")).strip()
    limit = min(max(int(payload.get("limit", 10)), 1), 50)
    if not query:
        raise ToolExecutionError("Search query is required.")

    course_id = str(payload.get("course_id", "")).strip() or None
    curriculum_course_id = str(payload.get("curriculum_course_id", "")).strip() or None
    pattern = f"%{query}%"
    course_filters = [Course.is_active.is_(True), or_(Course.name.ilike(pattern), Course.code.ilike(pattern))]
    if course_id:
        course_filters.append(Course.id == course_id)
    courses = db.scalars(
        select(Course)
        .where(*course_filters)
        .order_by(Course.name)
        .limit(limit)
    ).all()
    if curriculum_course_id:
        native_course = db.get(CurriculumCourse, curriculum_course_id)
        if native_course is None or not native_course.is_active:
            raise ToolExecutionError("TOFAN curriculum course not found.")
        native_units = db.scalars(
            select(CurriculumUnit)
            .where(
                CurriculumUnit.course_id == curriculum_course_id,
                CurriculumUnit.title.ilike(pattern),
            )
            .order_by(CurriculumUnit.position)
            .limit(limit)
        ).all()
        native_lessons = db.scalars(
            select(CurriculumLesson)
            .join(CurriculumUnit, CurriculumLesson.unit_id == CurriculumUnit.id)
            .where(
                CurriculumUnit.course_id == curriculum_course_id,
                CurriculumLesson.title.ilike(pattern),
            )
            .order_by(CurriculumLesson.position)
            .limit(limit)
        ).all()
        return json.dumps(
            {
                "query": query,
                "curriculum_course": {
                    "id": native_course.id,
                    "name": native_course.name,
                    "code": native_course.code,
                },
                "units": [
                    {"id": x.id, "course_id": x.course_id, "title": x.title}
                    for x in native_units
                ],
                "lessons": [
                    {"id": x.id, "unit_id": x.unit_id, "title": x.title, "position": x.position}
                    for x in native_lessons
                ],
            },
            ensure_ascii=False,
        )

    units = db.scalars(
        select(Unit).where(Unit.title.ilike(pattern)).order_by(Unit.position).limit(limit)
    ).all()
    lectures = db.scalars(
        select(Lecture)
        .where(Lecture.title.ilike(pattern), Lecture.status != "draft")
        .order_by(Lecture.title)
        .limit(limit)
    ).all()

    return json.dumps(
        {
            "query": query,
            "courses": [{"id": x.id, "name": x.name, "code": x.code} for x in courses],
            "units": [{"id": x.id, "course_id": x.course_id, "title": x.title} for x in units],
            "lectures": [{"id": x.id, "unit_id": x.unit_id, "title": x.title, "position": x.position} for x in lectures],
        },
        ensure_ascii=False,
    )


def manager_assessment_result_tool(db: Session, input_text: str) -> str:
    try:
        payload = json.loads(input_text or "{}")
        attempt_id = str(payload["attempt_id"])
    except (json.JSONDecodeError, KeyError) as exc:
        raise ToolExecutionError("attempt_id is required.") from exc
    try:
        result = MainManagerService.receive_assessment_result(db, attempt_id)
    except ValueError as exc:
        raise ToolExecutionError(str(exc)) from exc
    return json.dumps(result, ensure_ascii=False)


def manager_provision_teacher_tool(db: Session, input_text: str) -> str:
    try:
        payload = json.loads(input_text or "{}")
        course_id = str(payload["curriculum_course_id"])
    except (json.JSONDecodeError, KeyError) as exc:
        raise ToolExecutionError("curriculum_course_id is required.") from exc
    try:
        result = MainManagerService.provision_teacher(db, course_id)
    except ValueError as exc:
        raise ToolExecutionError(str(exc)) from exc
    return json.dumps(result, ensure_ascii=False)


def manager_set_teacher_status_tool(db: Session, input_text: str) -> str:
    try:
        payload = json.loads(input_text or "{}")
        agent_id = str(payload["agent_id"])
        status = AgentStatus(str(payload["status"]))
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise ToolExecutionError("Valid agent_id and status are required.") from exc
    try:
        result = MainManagerService.set_teacher_status(db, agent_id, status)
    except ValueError as exc:
        raise ToolExecutionError(str(exc)) from exc
    return json.dumps(result, ensure_ascii=False)


def manager_event_decision_tool(db: Session, input_text: str) -> str:
    try:
        payload = json.loads(input_text or "{}")
        event_name = str(payload["event_name"])
        actor_user_id = payload.get("actor_user_id")
        event_payload = dict(payload.get("payload") or {})
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ToolExecutionError("event_name and payload are required.") from exc
    try:
        result = MainManagerService.process_event(db, event_name, actor_user_id, event_payload)
    except ValueError as exc:
        raise ToolExecutionError(str(exc)) from exc
    return json.dumps(result, ensure_ascii=False)

def manager_teacher_overview_tool(db: Session, _: str) -> str:
    return json.dumps({"teachers": MainManagerService.teacher_overview(db)}, ensure_ascii=False)


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="academy.health",
            description="Return a simple runtime health result.",
            handler=health_tool,
        )
    )
    registry.register(
        ToolDefinition(
            name="academy.echo",
            description="Development-only echo tool.",
            handler=echo_tool,
        )
    )
    registry.register(
        ToolDefinition(
            name="academy.structure",
            description="Read the active academy institutional and academic-unit structure.",
            handler=academy_structure_tool,
        )
    )
    registry.register(
        ToolDefinition(
            name="academy.search",
            description="Search active courses, course units, and non-draft lectures by name or code.",
            handler=academy_search_tool,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The academy search query."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    "course_id": {"type": "string", "description": "Legacy course ID. Used only by legacy teacher agents."},
                    "curriculum_course_id": {"type": "string", "description": "Canonical TOFAN curriculum course ID. Required for TOFAN-native teacher agents."},
                },
                "required": ["query", "limit"],
                "additionalProperties": False,
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="education.assessment_result",
            description="Privileged manager action: receive and record a curriculum assessment result.",
            handler=manager_assessment_result_tool,
            sensitive=True,
            allowed_agent_slug="tofan-main",
            parameters={"type":"object","properties":{"attempt_id":{"type":"string"}},"required":["attempt_id"],"additionalProperties":False},
        )
    )
    registry.register(
        ToolDefinition(
            name="manager.provision_teacher",
            description="Privileged manager action: create the TOFAN-native AI teacher assigned to a curriculum course.",
            handler=manager_provision_teacher_tool,
            sensitive=True,
            allowed_agent_slug="tofan-main",
            parameters={"type":"object","properties":{"curriculum_course_id":{"type":"string"}},"required":["curriculum_course_id"],"additionalProperties":False},
        )
    )
    registry.register(
        ToolDefinition(
            name="manager.set_teacher_status",
            description="Privileged manager action: change an AI teacher status.",
            handler=manager_set_teacher_status_tool,
            sensitive=True,
            allowed_agent_slug="tofan-main",
            parameters={"type":"object","properties":{"agent_id":{"type":"string"},"status":{"type":"string","enum":["draft","active","paused","archived"]}},"required":["agent_id","status"],"additionalProperties":False},
        )
    )
    registry.register(
        ToolDefinition(
            name="manager.event_decision",
            description="Privileged manager action: evaluate a trusted system event, choose the appropriate operational decision, and persist the decision.",
            handler=manager_event_decision_tool,
            sensitive=True,
            allowed_agent_slug="tofan-main",
            parameters={
                "type": "object",
                "properties": {
                    "event_name": {"type": "string"},
                    "actor_user_id": {"type": ["string", "null"]},
                    "payload": {"type": "object"},
                },
                "required": ["event_name", "payload"],
                "additionalProperties": False,
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="manager.teacher_overview",
            description="Privileged manager action: inspect all AI teacher agents and their TOFAN course assignments.",
            handler=manager_teacher_overview_tool,
            sensitive=True,
            allowed_agent_slug="tofan-main",
            parameters={"type":"object","properties":{},"additionalProperties":False},
        )
    )
    registry.register(
        ToolDefinition(
            name="payments.confirm",
            description="Privileged action: confirm a genuinely verified payment transaction and activate global curriculum access.",
            handler=confirm_payment_tool,
            sensitive=True,
            allowed_agent_slug="tofan-main",
            parameters={
                "type": "object",
                "properties": {"transaction_id": {"type": "string"}},
                "required": ["transaction_id"],
                "additionalProperties": False,
            },
        )
    )
    return registry
