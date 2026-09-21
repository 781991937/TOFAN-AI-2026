"""Tool registry for the TOFAN agent runtime."""

import json
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.curriculum_models import CurriculumCourse, CurriculumLesson, CurriculumUnit
from app.db.models import AcademicUnit, Course, Institution, Lecture, Unit
from .payment_tools import confirm_payment_tool
from .main_manager import MainManagerService
from .models import AgentRole, AgentStatus


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


def health_tool(_: Session, _input_text: str) -> str:
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
    tokens = [token for token in query.split() if token]
    token_filters = []
    for token in tokens:
        token_pattern = f"%{token}%"
        token_filters.append(or_(Course.name.ilike(token_pattern), Course.code.ilike(token_pattern)))
    course_filters = [Course.is_active.is_(True), and_(*token_filters)] if token_filters else [Course.is_active.is_(True)]
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
                and_(*[CurriculumUnit.title.ilike(f"%{token}%") for token in tokens]) if tokens else CurriculumUnit.title.ilike(pattern),
            )
            .order_by(CurriculumUnit.position)
            .limit(limit)
        ).all()
        native_lessons = db.scalars(
            select(CurriculumLesson)
            .join(CurriculumUnit, CurriculumLesson.unit_id == CurriculumUnit.id)
            .where(
                CurriculumUnit.course_id == curriculum_course_id,
                and_(*[CurriculumLesson.title.ilike(f"%{token}%") for token in tokens]) if tokens else CurriculumLesson.title.ilike(pattern),
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


def manager_delegate_specialist_tool(db: Session, input_text: str) -> str:
    """Delegate a bounded task to an active specialist AI agent and return its result."""
    p = _payload(input_text)
    role_value = str(p.get("role", "")).strip()
    task = str(p.get("task", "")).strip()
    if not role_value or not task:
        raise ToolExecutionError("role and task are required.")
    try:
        role = AgentRole(role_value)
    except ValueError as exc:
        raise ToolExecutionError("Unsupported specialist role.") from exc
    if role in {AgentRole.GENERAL_MANAGER, AgentRole.TEACHER}:
        raise ToolExecutionError("Use a specialist role.")
    agent = db.scalar(select(Agent).where(
        Agent.role == role, Agent.status == AgentStatus.ACTIVE
    ).order_by(Agent.created_at))
    if agent is None:
        try:
            MainManagerService.provision_specialist(db, role)
        except ValueError as exc:
            raise ToolExecutionError(str(exc)) from exc
        agent = db.scalar(select(Agent).where(
            Agent.role == role, Agent.status == AgentStatus.ACTIVE
        ).order_by(Agent.created_at))
    if agent is None:
        raise ToolExecutionError("Specialist agent could not be provisioned.")
    from .llm import build_configured_provider
    from .providers import AgentMessage
    provider = build_configured_provider()
    enabled = [
        row.tool_name for row in db.scalars(
            select(__import__("app.agents.models", fromlist=["AgentTool"]).AgentTool)
            .where(
                __import__("app.agents.models", fromlist=["AgentTool"]).AgentTool.agent_id == agent.id,
                __import__("app.agents.models", fromlist=["AgentTool"]).AgentTool.enabled.is_(True),
            )
        ).all()
    ]
    definitions = build_default_registry().openai_definitions(enabled)
    run = __import__("app.agents.models", fromlist=["AgentRun"]).AgentRun(
        agent_id=agent.id, tool_name="workforce.delegate_task", status="running", input_text=task
    )
    db.add(run)
    db.flush()
    try:
        response = provider.generate(
            [AgentMessage(role="user", content=task)],
            system_prompt=agent.system_prompt,
            tools=definitions,
        )
        run.status = "completed"
        run.output_text = response.content or json.dumps(
            {"tool_calls": [x["name"] for x in response.tool_calls]}, ensure_ascii=False
        )
        run.completed_at = __import__("datetime").datetime.utcnow()
        db.commit()
        return json.dumps({
            "specialist_agent_id": agent.id,
            "specialist_role": agent.role,
            "status": "completed",
            "response": response.content,
        }, ensure_ascii=False)
    except Exception as exc:
        db.rollback()
        raise ToolExecutionError("Specialist delegation failed.") from exc


def manager_provision_specialist_tool(db: Session, input_text: str) -> str:
    p = _payload(input_text)
    role_value = str(p.get("role", "")).strip()
    if not role_value:
        raise ToolExecutionError("role is required.")
    try:
        role = AgentRole(role_value)
    except ValueError as exc:
        raise ToolExecutionError("Unsupported specialist role.") from exc
    try:
        result = MainManagerService.provision_specialist(
            db, role, name=p.get("name"), description=p.get("description")
        )
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

def _payload(input_text: str) -> dict:
    try:
        value = json.loads(input_text or "{}")
    except json.JSONDecodeError as exc:
        raise ToolExecutionError("Input must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise ToolExecutionError("Input must be a JSON object.")
    return value


def global_computing_curriculum_tool(_: Session, input_text: str) -> str:
    """Return the international CS curriculum reference used by the General Manager."""
    areas = [
        ("AL", "Algorithmic Foundations", "Software"),
        ("AR", "Architecture and Organization", "Systems"),
        ("AI", "Artificial Intelligence", "Applications"),
        ("DM", "Data Management", "Systems"),
        ("FPL", "Foundations of Programming Languages", "Software"),
        ("GIT", "Graphics and Interactive Techniques", "Applications"),
        ("HCI", "Human-Computer Interaction", "Applications"),
        ("MSF", "Mathematical and Statistical Foundations", "Software"),
        ("NC", "Networking and Communication", "Systems"),
        ("OS", "Operating Systems", "Systems"),
        ("PDC", "Parallel and Distributed Computing", "Systems"),
        ("SEC", "Security", "Systems"),
        ("SEP", "Society, Ethics, and the Profession", "Applications"),
        ("SDF", "Software Development Fundamentals", "Software"),
        ("SE", "Software Engineering", "Software"),
        ("SPD", "Specialized Platform Development", "Applications"),
        ("SF", "Systems Fundamentals", "Systems"),
    ]
    return json.dumps({
        "reference": "ACM/IEEE-CS/AAAI CS2023 + ACM/IEEE CC2020",
        "program_shape": "4 years / 8 semesters",
        "competency_areas": ["Software", "Systems", "Applications"],
        "knowledge_areas": [{"code": code, "name": name, "competency_area": group} for code, name, group in areas],
        "rule": "Use this as an international reference; adapt course packaging to the institution and never override an approved university study plan."
    }, ensure_ascii=False)


def manager_create_curriculum_tool(db: Session, input_text: str) -> str:
    from app.db.curriculum_models import Curriculum
    p = _payload(input_text)
    for key in ("slug", "name", "version"):
        if not str(p.get(key, "")).strip():
            raise ToolExecutionError(f"{key} is required.")
    item = Curriculum(slug=str(p["slug"]).strip(), name=str(p["name"]).strip(), version=str(p["version"]).strip(), description=p.get("description"))
    db.add(item)
    try: db.commit()
    except Exception as exc:
        db.rollback(); raise ToolExecutionError("Curriculum slug/version already exists.") from exc
    db.refresh(item)
    return json.dumps({"id":item.id,"slug":item.slug,"name":item.name,"version":item.version}, ensure_ascii=False)


def manager_create_specialty_tool(db: Session, input_text: str) -> str:
    from app.db.curriculum_models import Specialty
    p = _payload(input_text)
    for key in ("name", "code"):
        if not str(p.get(key, "")).strip(): raise ToolExecutionError(f"{key} is required.")
    item = Specialty(name=str(p["name"]).strip(), code=str(p["code"]).strip(), description=p.get("description"), name_ar=p.get("name_ar"), name_en=p.get("name_en"))
    db.add(item)
    try: db.commit()
    except Exception as exc:
        db.rollback(); raise ToolExecutionError("Specialty code already exists.") from exc
    db.refresh(item)
    return json.dumps({"id":item.id,"name":item.name,"code":item.code}, ensure_ascii=False)


def manager_create_stage_tool(db: Session, input_text: str) -> str:
    from app.db.curriculum_models import Curriculum, CurriculumStage, Specialty
    p = _payload(input_text)
    for key in ("curriculum_id","specialty_id","code","name","position"):
        if p.get(key) in (None,""): raise ToolExecutionError(f"{key} is required.")
    if db.get(Curriculum,str(p["curriculum_id"])) is None: raise ToolExecutionError("Curriculum not found.")
    if db.get(Specialty,str(p["specialty_id"])) is None: raise ToolExecutionError("Specialty not found.")
    item=CurriculumStage(curriculum_id=str(p["curriculum_id"]),specialty_id=str(p["specialty_id"]),code=str(p["code"]).strip(),name=str(p["name"]).strip(),position=max(1,int(p["position"])),description=p.get("description"))
    db.add(item)
    try: db.commit()
    except Exception as exc:
        db.rollback(); raise ToolExecutionError("Stage code already exists for this curriculum.") from exc
    db.refresh(item); return json.dumps({"id":item.id,"code":item.code,"name":item.name,"position":item.position},ensure_ascii=False)


def manager_create_course_tool(db: Session, input_text: str) -> str:
    from app.db.curriculum_models import CurriculumStage, CurriculumCourse
    p=_payload(input_text)
    for key in ("curriculum_id","stage_id","code","name","position"):
        if p.get(key) in (None,""): raise ToolExecutionError(f"{key} is required.")
    stage=db.get(CurriculumStage,str(p["stage_id"]))
    if stage is None or stage.curriculum_id != str(p["curriculum_id"]): raise ToolExecutionError("Stage does not belong to the selected curriculum.")
    item=CurriculumCourse(curriculum_id=str(p["curriculum_id"]),stage_id=str(p["stage_id"]),code=str(p["code"]).strip(),name=str(p["name"]).strip(),description=p.get("description"),course_type=str(p.get("course_type","required")),position=max(1,int(p["position"])))
    db.add(item)
    try: db.commit()
    except Exception as exc:
        db.rollback(); raise ToolExecutionError("Course code already exists.") from exc
    db.refresh(item); return json.dumps({"id":item.id,"code":item.code,"name":item.name,"position":item.position},ensure_ascii=False)


def manager_create_unit_tool(db: Session, input_text: str) -> str:
    from app.db.curriculum_models import CurriculumCourse, CurriculumUnit
    p=_payload(input_text)
    for key in ("course_id","title","position"):
        if p.get(key) in (None,""): raise ToolExecutionError(f"{key} is required.")
    if db.get(CurriculumCourse,str(p["course_id"])) is None: raise ToolExecutionError("Course not found.")
    item=CurriculumUnit(course_id=str(p["course_id"]),title=str(p["title"]).strip(),position=max(1,int(p["position"])))
    db.add(item); db.commit(); db.refresh(item)
    return json.dumps({"id":item.id,"course_id":item.course_id,"title":item.title,"position":item.position},ensure_ascii=False)


def manager_create_lesson_tool(db: Session, input_text: str) -> str:
    from app.db.curriculum_models import CurriculumUnit, CurriculumLesson
    p=_payload(input_text)
    for key in ("unit_id","title","position"):
        if p.get(key) in (None,""): raise ToolExecutionError(f"{key} is required.")
    if db.get(CurriculumUnit,str(p["unit_id"])) is None: raise ToolExecutionError("Unit not found.")
    item=CurriculumLesson(unit_id=str(p["unit_id"]),title=str(p["title"]).strip(),position=max(1,int(p["position"])),description=p.get("description"),content_markdown=p.get("content_markdown"))
    db.add(item); db.commit(); db.refresh(item)
    return json.dumps({"id":item.id,"unit_id":item.unit_id,"title":item.title,"position":item.position},ensure_ascii=False)




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
            name="manager.delegate_specialist",
            description="Delegate a bounded task to an active TOFAN specialist AI workforce agent and return its response.",
            handler=manager_delegate_specialist_tool,
            sensitive=False,
            allowed_agent_slug="tofan-main",
            parameters={
                "type": "object",
                "properties": {
                    "role": {"type": "string", "enum": [r.value for r in AgentRole if r not in {AgentRole.GENERAL_MANAGER, AgentRole.TEACHER}]},
                    "task": {"type": "string", "minLength": 1, "maxLength": 10000},
                },
                "required": ["role", "task"],
                "additionalProperties": False,
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="manager.provision_specialist",
            description="Privileged manager action: provision an AI specialist workforce agent for an approved operational domain.",
            handler=manager_provision_specialist_tool,
            sensitive=True,
            allowed_agent_slug="tofan-main",
            parameters={
                "type": "object",
                "properties": {
                    "role": {"type": "string", "enum": [r.value for r in AgentRole if r not in {AgentRole.GENERAL_MANAGER, AgentRole.TEACHER}]},
                    "name": {"type": ["string", "null"]},
                    "description": {"type": ["string", "null"]},
                },
                "required": ["role"],
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
            name="manager.global_computing_blueprint",
            description="Read the international computer-science curriculum reference based on ACM/IEEE-CS/AAAI CS2023 and CC2020. Use it when designing or checking a computing curriculum; it does not create records.",
            handler=global_computing_curriculum_tool,
            parameters={"type":"object","properties":{},"additionalProperties":False},
        )
    )
    for _tool in (
        ToolDefinition("manager.create_curriculum","Create a TOFAN curriculum after the Owner explicitly requests it.",manager_create_curriculum_tool,True,{"type":"object","properties":{"slug":{"type":"string"},"name":{"type":"string"},"version":{"type":"string"},"description":{"type":["string","null"]}},"required":["slug","name","version"],"additionalProperties":False},"tofan-main"),
        ToolDefinition("manager.create_specialty","Create an academic specialty.",manager_create_specialty_tool,True,{"type":"object","properties":{"name":{"type":"string"},"code":{"type":"string"},"description":{"type":["string","null"]},"name_ar":{"type":["string","null"]},"name_en":{"type":["string","null"]}},"required":["name","code"],"additionalProperties":False},"tofan-main"),
        ToolDefinition("manager.create_stage","Create a year/semester stage.",manager_create_stage_tool,True,{"type":"object","properties":{"curriculum_id":{"type":"string"},"specialty_id":{"type":"string"},"code":{"type":"string"},"name":{"type":"string"},"position":{"type":"integer","minimum":1},"description":{"type":["string","null"]}},"required":["curriculum_id","specialty_id","code","name","position"],"additionalProperties":False},"tofan-main"),
        ToolDefinition("manager.create_course","Create a course under a stage.",manager_create_course_tool,True,{"type":"object","properties":{"curriculum_id":{"type":"string"},"stage_id":{"type":"string"},"code":{"type":"string"},"name":{"type":"string"},"description":{"type":["string","null"]},"course_type":{"type":"string"},"position":{"type":"integer","minimum":1}},"required":["curriculum_id","stage_id","code","name","position"],"additionalProperties":False},"tofan-main"),
        ToolDefinition("manager.create_unit","Create a unit under a TOFAN course.",manager_create_unit_tool,True,{"type":"object","properties":{"course_id":{"type":"string"},"title":{"type":"string"},"position":{"type":"integer","minimum":1}},"required":["course_id","title","position"],"additionalProperties":False},"tofan-main"),
        ToolDefinition("manager.create_lesson","Create a lesson under a TOFAN unit.",manager_create_lesson_tool,True,{"type":"object","properties":{"unit_id":{"type":"string"},"title":{"type":"string"},"position":{"type":"integer","minimum":1},"description":{"type":["string","null"]},"content_markdown":{"type":["string","null"]}},"required":["unit_id","title","position"],"additionalProperties":False},"tofan-main"),
    ):
        registry.register(_tool)
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
