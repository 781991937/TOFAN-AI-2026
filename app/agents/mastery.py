"""Conversational mastery helpers for TOFAN teacher agents."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.agents.providers import AgentMessage, AIProvider
from app.db.models import TeachingStep


@dataclass(frozen=True)
class AnswerEvaluation:
    correct: bool
    feedback: str
    hint: str


_CONFIRM_WORDS = (
    "فهمت", "فاهم", "واضح", "تم الفهم", "تأكدت", "مفهوم",
    "نعم فهمت", "اي فهمت", "أيوه فهمت", "ايوه فهمت", "نعم، فهمت",
)


def is_explicit_confirmation(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().casefold())
    return any(word in normalized for word in _CONFIRM_WORDS)


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def evaluate_student_answer(
    provider: AIProvider,
    *,
    course_name: str,
    unit_title: str,
    lesson_title: str,
    check_question: str,
    student_answer: str,
    attempts: int,
) -> AnswerEvaluation:
    system = (
        "أنت مُقيّم فهم تعليمي في أكاديمية طوفان الذكية. "
        "قيّم إجابة الطالب بالنسبة للسؤال فقط وبصرامة تعليمية عادلة. "
        "لا تعتبر مجرد تكرار كلمات السؤال إجابة صحيحة. "
        "أعد JSON فقط بالمفاتيح: correct (boolean), feedback (string), hint (string). "
        "إذا كانت الإجابة صحيحة اجعل feedback تشجيعيًا ومختصرًا وhint فارغًا. "
        "إذا كانت خاطئة، لا تكشف الحل الكامل في hint؛ أعط تلميحًا يقود الطالب للتفكير. "
        "بعد المحاولة الثالثة، يمكن أن يكون feedback شارحًا للحل الصحيح باختصار."
    )
    prompt = (
        f"المقرر: {course_name}\nالوحدة: {unit_title}\nالدرس: {lesson_title}\n"
        f"سؤال الفهم: {check_question}\nإجابة الطالب: {student_answer}\n"
        f"رقم المحاولة الحالية: {attempts + 1}\n"
    )
    response = provider.generate(
        [AgentMessage(role="user", content=prompt)],
        system_prompt=system,
    )
    data = _extract_json(response.content)
    correct = bool(data.get("correct", False))
    feedback = str(data.get("feedback", "")).strip()
    hint = str(data.get("hint", "")).strip()
    if not feedback:
        feedback = "الإجابة تحتاج مراجعة. حاول ربطها مباشرة بمفهوم الدرس."
    if not hint and not correct:
        hint = "ارجع إلى الفكرة الأساسية في الدرس وحاول صياغتها بكلماتك."
    return AnswerEvaluation(correct=correct, feedback=feedback, hint=hint)


def mastery_instruction(step: TeachingStep) -> str:
    if step.status.value == "completed":
        return "الخطوة مكتملة. لا تعدها كخطوة جديدة."
    if step.understanding_verified and not step.student_confirmed:
        return (
            "تحقق الفهم. اطلب الآن من الطالب تأكيدًا صريحًا بأنه فهم الخطوة. "
            "لا تفتح الخطوة التالية قبل التأكيد."
        )
    if not step.understanding_verified:
        return (
            "الفهم لم يتحقق بعد. بعد الشرح اسأل سؤال فهم واحدًا فقط، "
            "ثم قيّم إجابة الطالب قبل أي انتقال."
        )
    return "أكمل الخطوة بعد تحقق الفهم والتأكيد الصريح.";
