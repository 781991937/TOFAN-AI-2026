from app.curriculum_registry import (
    get_curriculum,
    list_curricula,
    semester_courses,
    validate_registry,
)


def test_global_registry_contains_five_specialties():
    refs = list_curricula()
    assert {ref.specialty_id for ref in refs} == {"AI", "CS", "CYBER", "SE", "DS"}


def test_all_registered_curricula_have_eight_semesters():
    errors = validate_registry()
    assert errors == [], "\\n".join(errors)


def test_ai_legacy_stages_are_normalized_to_eight_semesters():
    curriculum = get_curriculum("AI")
    semesters = curriculum["semesters"]
    assert len(semesters) == 8
    assert {(x["year_number"], x["semester_number"]) for x in semesters} == {
        (year, semester) for year in range(1, 5) for semester in (1, 2)
    }
    assert semester_courses("AI", 1, 1)[0]["id"] == "AI-FND-001"


def test_registry_resolves_courses_dynamically():
    courses = semester_courses("CS", 1, 1)
    assert courses
    assert all(course["id"] and course["name_ar"] for course in courses)


def test_cs_tuple_courses_are_normalized_for_seeders():
    course = semester_courses("CS", 1, 1)[0]
    assert course["id"].startswith("CS-")
    assert course["name_ar"]


def test_unknown_specialty_is_rejected():
    try:
        get_curriculum("UNKNOWN")
        assert False, "unknown specialty must be rejected"
    except ValueError:
        pass
