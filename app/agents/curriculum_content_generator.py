"""TOFAN academic content generator: Generate -> Validate -> Save."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.agents.llm import build_configured_provider
from app.agents.providers import AIProvider, AgentMessage
from app.curriculum_registry import get_curriculum, list_curricula
from app.db.curriculum_models import Curriculum, CurriculumCourse, CurriculumLesson, CurriculumUnit, LearningOutcome
from app.db.models import AuditLog


class CurriculumContentGenerationError(RuntimeError):
    pass


def _json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("\`\`\`"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("\`\`\`", 1)[0].strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise CurriculumContentGenerationError("AI did not return a JSON object.")
    try:
        value = json.loads(raw[start:end + 1])
    except json.JSONDecodeError as exc:
        raise CurriculumContentGenerationError("AI returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise CurriculumContentGenerationError("AI returned a non-object JSON value.")
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()


def _registry_course(data: dict[str, Any], code: str) -> dict[str, Any] | None:
    for semester in data.get("semesters", []):
        for course in semester.get("courses", []):
            if _text(course.get("id")) == code:
                return course
    return None


def _existing_scope(db, course_id: str) -> dict[str, Any]:
    units = db.scalars(
        select(CurriculumUnit).where(CurriculumUnit.course_id == course_id).order_by(CurriculumUnit.position)
    ).all()
    result = []
    for unit in units:
        lessons = db.scalars(
            select(CurriculumLesson).where(CurriculumLesson.unit_id == unit.id).order_by(CurriculumLesson.position)
        ).all()
        result.append({
            "position": unit.position,
            "title": unit.title,
            "lessons": [
                {"position": l.position, "title": l.title, "has_content": bool(_text(l.content_markdown))}
                for l in lessons
            ],
        })
    return {"units": result}


def _targets(db, specialty_id: str | None) -> list[tuple[str, str, dict[str, Any], CurriculumCourse, dict[str, Any]]]:
    wanted = specialty_id.strip().upper() if specialty_id else None
    targets = []
    for ref in list_curricula():
        if wanted and ref.specialty_id.upper() != wanted:
            continue
        data = get_curriculum(ref.specialty_id)
        curriculum = db.scalar(select(Curriculum).where(
            Curriculum.slug == ref.curriculum_id,
            Curriculum.version == _text(data.get("version", "1.0")),
        ))
        if curriculum is None:
            continue
        courses = db.scalars(select(CurriculumCourse).where(
            CurriculumCourse.curriculum_id == curriculum.id,
            CurriculumCourse.is_active.is_(True),
        ).order_by(CurriculumCourse.position)).all()
        for course in courses:
            rc = _registry_course(data, course.code)
            if rc is None:
                continue
            units = db.scalars(select(CurriculumUnit).where(CurriculumUnit.course_id == course.id)).all()
            lessons = db.scalars(
                select(CurriculumLesson).join(CurriculumUnit, CurriculumLesson.unit_id == CurriculumUnit.id)
                .where(CurriculumUnit.course_id == course.id)
            ).all()
            outcomes = db.scalars(select(LearningOutcome).where(LearningOutcome.course_id == course.id)).all()
            if not units or not lessons or any(not _text(x.content_markdown) for x in lessons) or not outcomes:
                targets.append((ref.specialty_id, ref.curriculum_id, data, course, rc))
    return targets


def _prompt(specialty_id: str, curriculum_id: str, data: dict[str, Any], rc: dict[str, Any], scope: dict[str, Any]) -> tuple[str, str]:
    outcomes = rc.get("outcomes") or rc.get("learning_outcomes") or []
    system = """أنت مولّد المحتوى الأكاديمي الأصلي في أكاديمية طوفان الذكية.
المصدر الوحيد للهيكل هو TOFAN Global Curriculum. لا تنشئ مقررًا أو تخصصًا أو رمز مقرر جديدًا.
لا تنسخ من جامعة أو كتاب أو موقع، ولا تدّع مراجع لم تُعطَ لك.
اكتب المحتوى الجامعي بالعربية مع المصطلحات التقنية الإنجليزية عند الحاجة.
ركز على الفهم والتطبيق وحل المشكلات، وليس الحشو.
أخرج JSON فقط. كل درس يجب أن يكون شرحًا أكاديميًا حقيقيًا، مع أمثلة أو تطبيقات مناسبة، وأخطاء شائعة أو نقاط تحقق، وتمرين قصير.
"""
    user = {
        "specialty_id": specialty_id,
        "curriculum_id": curriculum_id,
        "course": {
            "code": rc.get("id"),
            "name_ar": rc.get("name_ar"),
            "description_ar": rc.get("description_ar"),
            "year_number": rc.get("year_number"),
            "semester_number": rc.get("semester_number"),
            "prerequisites": rc.get("prerequisites", []),
            "learning_outcomes": outcomes,
        },
        "reference_frameworks": data.get("reference_frameworks", []),
        "existing_scope": scope,
        "required_output": {
            "learning_outcomes": ["4-8 measurable outcomes only if DB has none"],
            "units": [{
                "position": 1,
                "title": "unit title",
                "lessons": [{
                    "position": 1,
                    "title": "lesson title",
                    "description": "lesson description",
                    "learning_objectives": ["objective 1", "objective 2"],
                    "content_markdown": "substantial original academic lesson in Markdown",
                }],
            }],
        },
        "rules": [
            "Preserve existing unit positions and titles exactly.",
            "Do not return existing lessons that already have content.",
            "For an existing unit with no lessons, create 2-6 lessons.",
            "For a course with no units, create 3-6 units and 2-6 lessons per unit.",
            "Use unique positions starting at 1.",
            "Never change the approved course code or name.",
        ],
    }
    return system, json.dumps(user, ensure_ascii=False)


def _validate(payload: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    units = payload.get("units")
    if not isinstance(units, list) or not units:
        raise CurriculumContentGenerationError("Generated course has no units.")
    existing = {u["position"]: u for u in scope["units"]}
    seen_units: set[int] = set()
    clean = []
    for raw_unit in units:
        if not isinstance(raw_unit, dict):
            raise CurriculumContentGenerationError("Invalid generated unit.")
        try:
            pos = int(raw_unit["position"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CurriculumContentGenerationError("Invalid unit position.") from exc
        if pos in seen_units:
            raise CurriculumContentGenerationError("Duplicate unit position.")
        seen_units.add(pos)
        title = existing[pos]["title"] if pos in existing else _text(raw_unit.get("title"))
        if not title:
            raise CurriculumContentGenerationError("Unit title is empty.")
        raw_lessons = raw_unit.get("lessons")
        if not isinstance(raw_lessons, list) or not raw_lessons:
            raise CurriculumContentGenerationError(f"Unit {pos} has no lessons.")
        existing_lessons = {x["position"]: x for x in existing.get(pos, {}).get("lessons", [])}
        seen_lessons: set[int] = set()
        clean_lessons = []
        for raw in raw_lessons:
            if not isinstance(raw, dict):
                raise CurriculumContentGenerationError("Invalid generated lesson.")
            try:
                lpos = int(raw["position"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CurriculumContentGenerationError("Invalid lesson position.") from exc
            if lpos in seen_lessons:
                raise CurriculumContentGenerationError("Duplicate lesson position.")
            seen_lessons.add(lpos)
            old = existing_lessons.get(lpos)
            if old and old["has_content"]:
                continue
            ltitle = _text(old["title"] if old else raw.get("title"))
            description = _text(raw.get("description"))
            objectives = [_text(x) for x in raw.get("learning_objectives", []) if _text(x)]
            content = _text(raw.get("content_markdown"))
            if not ltitle or len(content) < 350 or len(objectives) < 2:
                raise CurriculumContentGenerationError(f"Lesson {lpos} in unit {pos} failed validation.")
            lowered = content.lower()
            if "lorem ipsum" in lowered or "placeholder" in lowered:
                raise CurriculumContentGenerationError("Placeholder content detected.")
            clean_lessons.append({
                "position": lpos,
                "title": ltitle,
                "description": description[:2000] or None,
                "learning_objectives": objectives[:8],
                "content_markdown": content,
            })
        clean.append({"position": pos, "title": title, "lessons": clean_lessons})
    if not existing and not 3 <= len(clean) <= 6:
        raise CurriculumContentGenerationError("A new course must contain 3-6 units.")
    if existing and not set(existing).issubset(seen_units):
        raise CurriculumContentGenerationError("Existing unit structure was not preserved.")
    generated_outcomes = payload.get("learning_outcomes") or []
    if not isinstance(generated_outcomes, list):
        raise CurriculumContentGenerationError("learning_outcomes must be a list.")
    return {"units": clean, "learning_outcomes": [_text(x) for x in generated_outcomes if _text(x)]}


def _save(db, specialty_id: str, curriculum_id: str, data: dict[str, Any], course: CurriculumCourse, rc: dict[str, Any], result: dict[str, Any]) -> dict[str, int]:
    outcomes = db.scalars(select(LearningOutcome).where(LearningOutcome.course_id == course.id).order_by(LearningOutcome.position)).all()
    outcomes_created = 0
    if not outcomes:
        source = result["learning_outcomes"] or [_text(x) for x in (rc.get("outcomes") or rc.get("learning_outcomes") or []) if _text(x)]
        if not source:
            raise CurriculumContentGenerationError("No learning outcomes available.")
        for pos, statement in enumerate(source[:8], 1):
            db.add(LearningOutcome(course_id=course.id, statement=statement, position=pos))
            outcomes_created += 1
    created_units = created_lessons = updated_lessons = 0
    for unit_data in result["units"]:
        unit = db.scalar(select(CurriculumUnit).where(
            CurriculumUnit.course_id == course.id,
            CurriculumUnit.position == unit_data["position"],
        ))
        if unit is None:
            unit = CurriculumUnit(course_id=course.id, title=unit_data["title"], position=unit_data["position"])
            db.add(unit)
            db.flush()
            created_units += 1
        for lesson_data in unit_data["lessons"]:
            lesson = db.scalar(select(CurriculumLesson).where(
                CurriculumLesson.unit_id == unit.id,
                CurriculumLesson.position == lesson_data["position"],
            ))
            if lesson is None:
                lesson = CurriculumLesson(unit_id=unit.id, title=lesson_data["title"], position=lesson_data["position"])
                db.add(lesson)
                created_lessons += 1
            elif _text(lesson.content_markdown):
                continue
            else:
                updated_lessons += 1
            lesson.title = lesson_data["title"]
            lesson.description = lesson_data["description"]
            lesson.content_markdown = lesson_data["content_markdown"]
            lesson.learning_objectives_json = json.dumps(lesson_data["learning_objectives"], ensure_ascii=False)
            lesson.source_refs_json = json.dumps(
                ["TOFAN Global Curriculum Registry", *data.get("reference_frameworks", [])], ensure_ascii=False
            )
    db.add(AuditLog(
        action="ai_curriculum_content_generated",
        resource_type="curriculum_course",
        resource_id=course.id,
        details=json.dumps({
            "specialty_id": specialty_id,
            "curriculum_id": curriculum_id,
            "course_code": course.code,
            "created_units": created_units,
            "created_lessons": created_lessons,
            "updated_lessons": updated_lessons,
            "learning_outcomes_created": outcomes_created,
        }, ensure_ascii=False),
    ))
    db.commit()
    return {"created_units": created_units, "created_lessons": created_lessons, "updated_lessons": updated_lessons, "learning_outcomes_created": outcomes_created}


def generate_next_courses(db, *, specialty_id: str | None = None, max_courses: int = 1, provider: AIProvider | None = None) -> dict[str, Any]:
    """Generate the next missing courses automatically; rerunning resumes safely."""
    max_courses = max(1, min(int(max_courses), 5))
    targets = _targets(db, specialty_id)
    if not targets:
        return {"status": "complete", "processed": 0, "remaining": 0, "message": "All registered TOFAN curriculum courses have persisted content."}
    provider = provider or build_configured_provider()
    processed, failed = [], []
    for specialty, curriculum_id, data, course, rc in targets[:max_courses]:
        scope = _existing_scope(db, course.id)
        system, user = _prompt(specialty, curriculum_id, data, rc, scope)
        try:
            response = provider.generate([AgentMessage(role="user", content=user)], system_prompt=system)
            validated = _validate(_json(response.content), scope)
            savepoint = db.begin_nested()
            try:
                saved = _save(db, specialty, curriculum_id, data, course, rc, validated)
                savepoint.commit()
            except Exception:
                savepoint.rollback()
                raise
            processed.append({"specialty_id": specialty, "curriculum_id": curriculum_id, "course_id": course.id, "course_code": course.code, **saved})
        except Exception as exc:
            db.rollback()
            failed.append({"specialty_id": specialty, "curriculum_id": curriculum_id, "course_id": course.id, "course_code": course.code, "error": str(exc)})
    remaining = len(_targets(db, specialty_id))
    return {
        "status": "complete" if remaining == 0 and not failed else "partial",
        "processed": len(processed),
        "failed": failed,
        "remaining": remaining,
        "results": processed,
        "next_action": "شغّل manager.generate_global_curriculum_content مرة أخرى للمتابعة." if remaining else None,
    }
