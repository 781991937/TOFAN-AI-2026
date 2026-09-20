"""Teacher-agent profiles, course assignment, and teaching policy."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AcademicUnit, Course, Institution
from .models import Agent, AgentKind, AgentStatus, AgentTool


DEFAULT_TEACHER_PROMPT = """أنت مدرس ذكاء اصطناعي داخل أكاديمية طوفان الذكية.
مهمتك التعليم والفهم، وليس ادعاء أنك أستاذ جامعي رسمي أو إصدار قرارات أكاديمية.
التزم بالمقرر والمحتوى المعتمد المرتبط بالمادة التي تم تعيينك لها عندما يكون المحتوى متاحًا.
ابدأ من الصفر ولا تفترض معرفة سابقة.
عرّف أي مصطلح جديد قبل استخدامه.
اشرح خطوة بخطوة، وبأسلوب واضح، وركّز على الفهم والتطبيق والاستنتاج.
لا تخترع محاضرات أو مقررات أو معلومات غير موجودة في المحتوى المعتمد.
عند التدريب: اسأل سؤالًا واحدًا في كل مرة. إذا أخطأ الطالب، أعطِ تلميحًا يساعده على التصحيح، ولا تكشف الإجابة مباشرة. بعد ثلاث محاولات يمكن كشف الإجابة الصحيحة مع شرح السبب.
افصل بين وضع الشرح ووضع الاختبار.
احترم صلاحيات الوصول للمحتوى وذاكرة الطالب ولا تكشف معلومات تخص وكيلًا أو مادة أخرى."""


@dataclass(frozen=True)
class TeacherAgentProfile:
    agent_id: str
    course_id: str
    teaching_language: str
    policy_version: str = "1"


def create_teacher_agent(
    db: Session,
    *,
    name: str,
    slug: str,
    course_id: str,
    description: str | None = None,
    teaching_language: str = "ar",
) -> Agent:
    course = db.get(Course, course_id)
    if course is None or not course.is_active:
        raise ValueError("Active course not found.")

    existing = db.scalar(select(Agent).where(Agent.slug == slug))
    if existing is not None:
        raise ValueError("Agent slug already exists.")

    agent = Agent(
        name=name.strip(),
        slug=slug.strip(),
        kind=AgentKind.TEACHER,
        status=AgentStatus.DRAFT,
        description=description or f"AI teacher for course: {course.name}",
        system_prompt=DEFAULT_TEACHER_PROMPT,
        model_provider="openai",
        model_name=None,
        memory_enabled=True,
        teacher_course_id=course_id,
        teacher_institution_id=None,
    )
    db.add(agent)
    db.flush()
    unit = db.get(AcademicUnit, course.academic_unit_id)
    if unit is not None:
        agent.teacher_institution_id = unit.institution_id
    db.add(AgentTool(agent_id=agent.id, tool_name="academy.search", enabled=True))
    db.flush()
    return agent



def provision_teacher_agents_for_institution(
    db: Session,
    *,
    institution_id: str,
) -> list[Agent]:
    """Create draft AI teachers for every existing course in an institution.

    No human instructor is created or assigned. Each course receives its own
    independent AI teacher agent. The operation is idempotent.
    """
    institution = db.get(Institution, institution_id)
    if institution is None or not institution.is_active:
        raise ValueError("Active institution not found.")

    courses = db.scalars(
        select(Course)
        .join(AcademicUnit, AcademicUnit.id == Course.academic_unit_id)
        .where(
            AcademicUnit.institution_id == institution_id,
            AcademicUnit.is_active.is_(True),
            Course.is_active.is_(True),
        )
        .order_by(Course.name)
    ).all()

    created: list[Agent] = []
    for course in courses:
        slug = f"teacher-{institution.code or institution.id[:8]}-{course.id[:8]}"
        existing = db.scalar(select(Agent).where(Agent.slug == slug))
        if existing is not None:
            continue
        agent = create_teacher_agent(
            db,
            name=f"مدرس {course.name}",
            slug=slug,
            course_id=course.id,
            description=f"وكيل مدرس ذكاء اصطناعي لمادة {course.name} في {institution.name}.",
        )
        agent.teacher_institution_id = institution_id
        created.append(agent)

    db.flush()
    return created

def get_teacher_profile(db: Session, agent: Agent) -> TeacherAgentProfile:
    course_id = getattr(agent, "teacher_course_id", None)
    if not course_id:
        raise ValueError("Teacher agent is not assigned to a course.")
    return TeacherAgentProfile(
        agent_id=agent.id,
        course_id=course_id,
        teaching_language="ar",
    )
