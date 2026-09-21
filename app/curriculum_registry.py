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
            return curriculum
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
        for semester in curriculum.get("semesters", []):
            pair = (semester.get("year_number"), semester.get("semester_number"))
            if pair in seen:
                errors.append(f"Duplicate semester {pair} in {ref['specialty_id']}.")
            seen.add(pair)
            if not semester.get("courses"):
                errors.append(f"Empty semester {pair} in {ref['specialty_id']}.")
            for course in semester.get("courses", []):
                if not course.get("id") or not course.get("name_ar"):
                    errors.append(f"Invalid course in {ref['specialty_id']} semester {pair}.")
        missing = expected_semesters - seen
        if missing:
            errors.append(
                f"Missing semesters in {ref['specialty_id']}: {sorted(missing)}."
            )
    return errors
