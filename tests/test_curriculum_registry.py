"""Validation tests for the five canonical TOFAN global specialty curricula."""

from app.curriculum_registry import list_curricula, validate_registry


EXPECTED = {
    "AI": 42,
    "CS": 45,
    "CYBER": 46,
    "SE": 45,
    "DS": 45,
}


def test_global_registry_has_five_specialties():
    refs = list_curricula()
    assert {ref.specialty_id for ref in refs} == set(EXPECTED)


def test_global_curricula_are_normalized_to_eight_semesters():
    assert validate_registry() == []


def test_global_curriculum_course_counts_are_canonical():
    from app.curriculum_registry import get_curriculum

    for specialty_id, expected_count in EXPECTED.items():
        curriculum = get_curriculum(specialty_id)
        semesters = curriculum["semesters"]
        assert len(semesters) == 8
        assert len({
            (item["year_number"], item["semester_number"])
            for item in semesters
        }) == 8
        assert sum(len(item["courses"]) for item in semesters) == expected_count
