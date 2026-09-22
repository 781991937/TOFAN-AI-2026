"""TOFAN global curriculum registry and loader.

Curricula are data-driven JSON files. This module keeps the application
independent from any single university and exposes one dynamic registry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "docs" / "curricula" / "specialty_structure_v1.json"


class CurriculumError(ValueError):
    """Raised when the curriculum registry or a curriculum is invalid."""


@dataclass(frozen=True)
class CurriculumRef:
    specialty_id: str
    curriculum_id: str
    path: str


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CurriculumError(f"Curriculum file not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CurriculumError(f"Invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CurriculumError(f"Curriculum root must be an object: {path}")
    return value


def load_registry() -> dict[str, Any]:
    registry = _load_json(REGISTRY_PATH)
    refs = registry.get("curriculum_registry")
    if not isinstance(refs, list):
        raise CurriculumError("Registry must contain curriculum_registry.")
    return registry


def list_curricula() -> list[CurriculumRef]:
    refs = load_registry()["curriculum_registry"]
    return [
        CurriculumRef(
            specialty_id=item["specialty_id"],
            curriculum_id=item["curriculum_id"],
            path=item["path"],
        )
        for item in refs
    ]


def _normalize_curriculum(curriculum: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical semester representation used by TOFAN APIs/seeders."""
    def normalize_course(course: Any) -> dict[str, Any] | None:
        if isinstance(course, dict):
            item = dict(course)
        elif isinstance(course, (list, tuple)) and course:
            item = {
                "id": str(course[0]),
                "name_ar": str(course[1]) if len(course) > 1 else str(course[0]),
            }
        else:
            return None
        item.setdefault("name_ar", item.get("name_en") or item.get("id", ""))
        item.setdefault("name_en", item.get("name_ar", ""))
        item.setdefault("description_ar", item.get("description") or "")
        item.setdefault("description_en", item.get("description") or "")
        item.setdefault("prerequisites", [])
        item.setdefault("learning_outcomes", item.get("outcomes", []))
        return item

    existing_semesters = curriculum.get("semesters")
    if isinstance(existing_semesters, list) and existing_semesters:
        normalized = dict(curriculum)
        normalized["semesters"] = []
        for semester in existing_semesters:
            if not isinstance(semester, dict):
                continue
            item = dict(semester)
            item["courses"] = [
                normalized_course
                for course in (semester.get("courses") or [])
                if (normalized_course := normalize_course(course)) is not None
            ]
            normalized["semesters"].append(item)
        return normalized

    stages = curriculum.get("stages") or []
    plan = curriculum.get("semester_plan") or []
    courses_by_id: dict[str, dict[str, Any]] = {}
    for stage in stages:
        for course in stage.get("courses", []):
            if isinstance(course, dict) and course.get("id"):
                courses_by_id[course["id"]] = dict(course)

    semesters: list[dict[str, Any]] = []
    if plan:
        for item in plan:
            year = int(item["year_number"])
            sem = int(item["semester_number"])
            courses = [
                courses_by_id[course_id]
                for course_id in item.get("course_ids", [])
                if course_id in courses_by_id
            ]
            semesters.append({
                "year_number": year,
                "semester_number": sem,
                "title_ar": item.get("title_ar", f"السنة {year} — الفصل {sem}"),
                "courses": courses,
            })
    else:
        grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for course in courses_by_id.values():
            if "year_number" in course and "semester_number" in course:
                key = (int(course["year_number"]), int(course["semester_number"]))
                grouped.setdefault(key, []).append(course)
        for year in range(1, 5):
            for sem in (1, 2):
                semesters.append({
                    "year_number": year,
                    "semester_number": sem,
                    "title_ar": f"السنة {year} — الفصل {sem}",
                    "courses": grouped.get((year, sem), []),
                })

    normalized = dict(curriculum)
    normalized["semesters"] = semesters
    return normalized


def get_curriculum(specialty_id: str) -> dict[str, Any]:
    key = specialty_id.strip().upper()
    for ref in list_curricula():
        if ref.specialty_id.upper() == key:
            curriculum = _load_json(REPO_ROOT / ref.path)
            if curriculum.get("curriculum_id") != ref.curriculum_id:
                raise CurriculumError(
                    f"Curriculum id mismatch for {ref.specialty_id}: "
                    f"{curriculum.get('curriculum_id')} != {ref.curriculum_id}"
                )
            return _normalize_curriculum(curriculum)
    raise CurriculumError(f"Unknown specialty: {specialty_id}")
def semester_courses(specialty_id: str, year: int, semester: int) -> list[dict[str, Any]]:
    curriculum = get_curriculum(specialty_id)
    for item in curriculum.get("semesters", []):
        if item.get("year_number") == year and item.get("semester_number") == semester:
            return list(item.get("courses", []))
    raise CurriculumError(
        f"Semester {year}-{semester} does not exist for {specialty_id.upper()}."
    )


def validate_registry() -> list[str]:
    errors: list[str] = []
    registry = load_registry()
    refs = registry.get("curriculum_registry", [])
    expected_semesters = {
        (year, semester) for year in range(1, 5) for semester in (1, 2)
    }

    for ref in refs:
        try:
            curriculum = get_curriculum(ref["specialty_id"])
        except CurriculumError as exc:
            errors.append(str(exc))
            continue

        seen: set[tuple[int, int]] = set()
        course_ids: set[str] = set()
        expected_course_ids: set[str] = set()
        for semester in curriculum.get("semesters", []):
            pair = (semester.get("year_number"), semester.get("semester_number"))
            if pair in seen:
                errors.append(f"Duplicate semester {pair} in {ref['specialty_id']}.")
            seen.add(pair)
            if pair not in expected_semesters:
                errors.append(f"Invalid semester {pair} in {ref['specialty_id']}.")
            courses = semester.get("courses") or []
            if not courses:
                errors.append(f"Empty semester {pair} in {ref['specialty_id']}.")
            for course in courses:
                code = course.get("id")
                if not code or not course.get("name_ar"):
                    errors.append(f"Invalid course in {ref['specialty_id']} semester {pair}.")
                    continue
                if code in course_ids:
                    errors.append(f"Duplicate course {code} in {ref['specialty_id']}.")
                course_ids.add(code)
                expected_course_ids.add(code)

        missing = expected_semesters - seen
        if missing:
            errors.append(
                f"Missing semesters in {ref['specialty_id']}: {sorted(missing)}."
            )

        expected_total = curriculum.get("expected_course_count")
        if expected_total is not None and len(course_ids) != int(expected_total):
            errors.append(
                f"Course count mismatch in {ref['specialty_id']}: "
                f"{len(course_ids)} != {expected_total}."
            )

        for semester in curriculum.get("semesters", []):
            for course in semester.get("courses", []):
                for prereq in course.get("prerequisites", []) or []:
                    if prereq not in course_ids:
                        errors.append(
                            f"Unknown prerequisite {prereq} for {course.get('id')} "
                            f"in {ref['specialty_id']}."
                        )
    return errors
