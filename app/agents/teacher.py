"""Teacher-agent profiles, course assignment, and teaching policy."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.curriculum_models import CurriculumCourse, CurriculumStage, LearningOutcome, CoursePrerequisite
from app.db.models import AcademicUnit, Course, Institution
from .models import Agent, AgentKind, AgentStatus, AgentTool


DEFAULT_TEACHER_PROMPT = """أنت مدرس ذكاء اصطناعي داخل أكاديمية طوفان الذكية.
مهمتك التعليم والفهم، وليس ادعاء أنك أستاذ جامعي رسمي أو إصدار قرارات أكاديمية.
المقرر الأساسي الذي تدرّسه هو مقرر TOFAN-native المعيّن لك، وليس جامعة بعينها.
يمكن استخدام بيانات الجامعات فقط كسياق مواءمة اختياري عند الحاجة.
ابدأ من الصفر ولا تفترض معرفة سابقة.
عرّف أي مصطلح جديد قبل استخدامه.
اشرح خطوة بخطوة، وبأسلوب واضح، وركّز على الفهم والتطبيق والاستنتاج.
لا تخترع محاضرات أو مقررات أو معلومات غير موجودة في المنهج أو المحتوى المعتمد.
عند التدريب: اسأل سؤال فهم واحدًا فقط في كل مرة. لا تعتبر الخطوة مكتملة من كلامك أنت؛ يجب أن يسجل النظام تحقق الفهم ثم يطلب تأكيدًا صريحًا من الطالب. إذا أخطأ الطالب، أعطِ تلميحًا يساعده على التصحيح. بعد ثلاث محاولات، اشرح التصحيح ثم اطلب من الطالب أن يشرح الفكرة بكلماته، ولا تعتبر ذلك تحققًا للفهم إلا بعد إجابة صحيحة وتسجيلها من النظام. لا تنتقل للخطوة التالية قبل تحقق الفهم وتأكيد الطالب.
افصل بين وضع الشرح ووضع الاختبار.
احترم صلاحيات الوصول للمحتوى وذاكرة الطالب ولا تكشف معلومات تخص وكيلًا أو مادة أخرى."""


@dataclass(frozen=True)
class TeacherAgentProfile:
    agent_id: str
    curriculum_course_id: str
    teaching_language: str
    policy_version: str = "2"


def create_curriculum_teacher_agent(
    db: Session,
    *,
    name: str,
    slug: str,
    curriculum_course_id: str,
    description: str | None = None,
    teaching_language: str = "ar",
) -> Agent:
    course = db.get(CurriculumCourse, curriculum_course_id)
    if course is None or not course.is_active:
        raise ValueError("Active TOFAN curriculum course not found.")

    existing = db.scalar(select(Agent).where(Agent.slug == slug))
    if existing is not None:
        raise ValueError("Agent slug already exists.")

    stage = db.get(CurriculumStage, course.stage_id)
    outcomes = db.scalars(
        select(LearningOutcome)
        .where(LearningOutcome.course_id == course.id)
        .order_by(LearningOutcome.position)
    ).all()
    prerequisites = db.scalars(
        select(CoursePrerequisite)
        .where(CoursePrerequisite.course_id == course.id)
    ).all()

    context = (
        f"\n\nمقرر TOFAN: {course.code} — {course.name}"
        f"\nالمرحلة: {stage.name if stage else 'غير محددة'}"
        f"\nالمخرجات التعليمية: "
        + ("؛ ".join(x.statement for x in outcomes) if outcomes else "غير محددة")
        + f"\nعدد المتطلبات السابقة: {len(prerequisites)}"
    )

    agent = Agent(
        name=name.strip(),
        slug=slug.strip(),
        kind=AgentKind.TEACHER,
        status=AgentStatus.DRAFT,
        description=description or f"AI teacher for TOFAN course: {course.name}",
        system_prompt=DEFAULT_TEACHER_PROMPT + context,
        model_provider="openai",
        model_name=None,
        memory_enabled=True,
        curriculum_course_id=curriculum_course_id,
        teacher_course_id=None,
        teacher_institution_id=None,
    )
    db.add(agent)
    db.flush()
    db.add(AgentTool(agent_id=agent.id, tool_name="academy.search", enabled=True))
    db.flush()
    return agent


def create_teacher_agent(
    db: Session,
    *,
    name: str,
    slug: str,
    course_id: str,
    description: str | None = None,
    teaching_language: str = "ar",
) -> Agent:
    """Legacy university-course teacher creation retained for migration compatibility."""
    course = db.get(Course, course_id)
    if course is None or not course.is_active:
        raise ValueError("Active legacy course not found.")

    existing = db.scalar(select(Agent).where(Agent.slug == slug))
    if existing is not None:
        raise ValueError("Agent slug already exists.")

    agent = Agent(
        name=name.strip(),
        slug=slug.strip(),
        kind=AgentKind.TEACHER,
        status=AgentStatus.DRAFT,
        description=description or f"Legacy AI teacher for course: {course.name}",
        system_prompt=DEFAULT_TEACHER_PROMPT,
        model_provider="openai",
        model_name=None,
        memory_enabled=True,
        teacher_course_id=course_id,
        curriculum_course_id=None,
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


def provision_teacher_agents_for_curriculum(
    db: Session,
    *,
    curriculum_slug: str,
) -> list[Agent]:
    from app.db.curriculum_models import Curriculum

    curriculum = db.scalar(
        select(Curriculum).where(Curriculum.slug == curriculum_slug, Curriculum.status == "active")
    )
    if curriculum is None:
        raise ValueError("Active TOFAN curriculum not found.")

    courses = db.scalars(
        select(CurriculumCourse)
        .where(CurriculumCourse.curriculum_id == curriculum.id, CurriculumCourse.is_active.is_(True))
        .order_by(CurriculumCourse.position, CurriculumCourse.name)
    ).all()

    created: list[Agent] = []
    for course in courses:
        slug = f"teacher-tofan-{course.code.lower()}"
        if db.scalar(select(Agent).where(Agent.slug == slug)) is not None:
            continue
        created.append(create_curriculum_teacher_agent(
            db,
            name=f"مدرس {course.name}",
            slug=slug,
            curriculum_course_id=course.id,
            description=f"وكيل مدرس ذكاء اصطناعي لمقرر TOFAN {course.code}: {course.name}.",
        ))
    db.flush()
    return created


def provision_teacher_agents_for_institution(
    db: Session,
    *,
    institution_id: str,
) -> list[Agent]:
    """Legacy reference-alignment provisioning. New TOFAN teachers use the curriculum catalog."""
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
        slug = f"teacher-legacy-{institution.code or institution.id[:8]}-{course.id[:8]}"
        if db.scalar(select(Agent).where(Agent.slug == slug)) is not None:
            continue
        agent = create_teacher_agent(
            db,
            name=f"مدرس {course.name}",
            slug=slug,
            course_id=course.id,
            description=f"وكيل مواءمة قديم لمادة {course.name} في {institution.name}.",
        )
        agent.teacher_institution_id = institution_id
        created.append(agent)
    db.flush()
    return created


def get_teacher_profile(db: Session, agent: Agent) -> TeacherAgentProfile:
    course_id = getattr(agent, "curriculum_course_id", None)
    if not course_id:
        raise ValueError("Teacher agent is not assigned to a TOFAN curriculum course.")
    return TeacherAgentProfile(
        agent_id=agent.id,
        curriculum_course_id=course_id,
        teaching_language="ar",
    )
