import json

from app.agents.curriculum_content_generator import _validate


def test_generated_curriculum_payload_is_validated():
    scope = {"units": []}
    payload = {
        "learning_outcomes": ["يفهم المفهوم.", "يطبقه."],
        "units": [
            {
                "position": 1,
                "title": "Unit 1",
                "lessons": [
                    {
                        "position": 1,
                        "title": "Lesson 1",
                        "description": "Intro",
                        "learning_objectives": ["Understand.", "Apply."],
                        "content_markdown": "# Lesson 1\n\n" + ("Academic explanation with examples and an application exercise. " * 12),
                    }
                ],
            },
            {
                "position": 2,
                "title": "Unit 2",
                "lessons": [
                    {
                        "position": 1,
                        "title": "Lesson 2",
                        "description": "Practice",
                        "learning_objectives": ["Analyze.", "Apply."],
                        "content_markdown": "# Lesson 2\n\n" + ("Academic explanation with examples and an application exercise. " * 12),
                    }
                ],
            },
            {
                "position": 3,
                "title": "Unit 3",
                "lessons": [
                    {
                        "position": 1,
                        "title": "Lesson 3",
                        "description": "Integration",
                        "learning_objectives": ["Design.", "Evaluate."],
                        "content_markdown": "# Lesson 3\n\n" + ("Academic explanation with examples and an application exercise. " * 12),
                    }
                ],
            },
        ],
    }
    result = _validate(payload, scope)
    assert len(result["units"]) == 3
    assert len(result["learning_outcomes"]) == 2


def test_invalid_generated_lesson_is_rejected():
    scope = {"units": []}
    payload = {
        "learning_outcomes": ["Outcome"],
        "units": [
            {
                "position": 1,
                "title": "Unit 1",
                "lessons": [
                    {
                        "position": 1,
                        "title": "Lesson 1",
                        "learning_objectives": ["Only one"],
                        "content_markdown": "short",
                    }
                ],
            }
        ],
    }
    try:
        _validate(payload, scope)
    except Exception as exc:
        assert "validation" in str(exc).lower()
    else:
        raise AssertionError("Invalid generated content must be rejected")
