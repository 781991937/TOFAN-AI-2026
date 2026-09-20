"""AI-generated curriculum assessment questions and deterministic grading."""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.agents.llm import build_configured_provider
from app.agents.providers import AgentMessage, AIProvider
from app.db.curriculum_models import CurriculumCourse, CurriculumLesson, CurriculumUnit, LearningOutcome

@dataclass(frozen=True)
class GeneratedQuestion:
    position: int
    question_type: str
    prompt: str
    options: list[str]
    correct_answer: str
    explanation: str
    points: float

def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("\n", 1)
        text = parts[1] if len(parts) == 2 else text
        text = text.rsplit("```", 1)[0]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Assessment generator returned no JSON object.")
    return json.loads(text[start:end + 1])

def generate_assessment_questions(*, db, course: CurriculumCourse, provider: AIProvider | None = None, question_count: int = 20) -> list[GeneratedQuestion]:
    provider = provider or build_configured_provider()
    units = db.query(CurriculumUnit).filter(CurriculumUnit.course_id == course.id).order_by(CurriculumUnit.position).all()
    lessons: list[CurriculumLesson] = []
    for unit in units:
        lessons.extend(db.query(CurriculumLesson).filter(CurriculumLesson.unit_id == unit.id).order_by(CurriculumLesson.position).all())
    outcomes = db.query(LearningOutcome).filter(LearningOutcome.course_id == course.id).order_by(LearningOutcome.position).all()
    scope = {"course": {"code": course.code, "name": course.name, "description": course.description}, "units": [{"position": u.position, "title": u.title} for u in units], "lessons": [{"unit_id": l.unit_id, "position": l.position, "title": l.title, "description": l.description} for l in lessons], "learning_outcomes": [o.statement for o in outcomes]}
    system = "أنت مولّد اختبارات أكاديمية لمنصة أكاديمية طوفان الذكية. أنشئ الاختبار من محتوى المقرر المعطى فقط. أخرج JSON صالحاً فقط بمفتاح questions. استخدم true_false و mcq فقط. للـ mcq أربعة خيارات وإجابة صحيحة واحدة. قِس الفهم والتطبيق ووزّع الأسئلة على الوحدات والدروس المتاحة."
    user = "عدد الأسئلة المطلوب: " + str(question_count) + "\nبيانات المنهج:\n" + json.dumps(scope, ensure_ascii=False)
    response = provider.generate([AgentMessage(role="user", content=user)], system_prompt=system)
    payload = _extract_json(response.content)
    raw = payload.get("questions")
    if not isinstance(raw, list) or len(raw) < question_count:
        raise ValueError("Assessment generator returned too few questions.")
    questions: list[GeneratedQuestion] = []
    for index, item in enumerate(raw[:question_count], start=1):
        qtype = str(item.get("type", "")).strip()
        prompt = str(item.get("prompt", "")).strip()
        options = [str(x).strip() for x in item.get("options", [])]
        answer = str(item.get("correct_answer", "")).strip()
        explanation = str(item.get("explanation", "")).strip()
        points = float(item.get("points", 1))
        if qtype not in {"true_false", "mcq"} or not prompt or not answer:
            raise ValueError("Assessment generator returned an invalid question.")
        if qtype == "true_false":
            options = ["صح", "خطأ"]
        elif len(options) != 4 or answer not in options:
            raise ValueError("Assessment generator returned an invalid MCQ.")
        questions.append(GeneratedQuestion(index, qtype, prompt, options, answer, explanation, points))
    return questions

def grade_answers(questions, answers: dict[str, str]) -> tuple[float, float, dict[str, dict]]:
    score = 0.0
    max_score = sum(float(q.points) for q in questions)
    details: dict[str, dict] = {}
    for q in questions:
        submitted = str(answers.get(str(q.position), "")).strip()
        correct = submitted == q.correct_answer
        if correct:
            score += float(q.points)
        details[str(q.position)] = {"correct": correct, "submitted_answer": submitted, "correct_answer": q.correct_answer, "explanation": q.explanation}
    return score, max_score, details