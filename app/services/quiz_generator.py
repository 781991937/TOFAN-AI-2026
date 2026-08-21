import json

from .ai_service import AIService


class QuizGenerator:
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service

    async def create(self, text: str, count: int = 10, difficulty: str = "medium") -> list[dict]:
        if not text.strip():
            raise ValueError("Lesson text is empty")
        count = max(1, min(count, 30))
        questions = await self.ai_service.generate_questions(text, count, difficulty)
        if not questions:
            raise RuntimeError("AI did not return any questions")
        return questions

    @staticmethod
    def serialize(questions: list[dict]) -> str:
        return json.dumps(questions, ensure_ascii=False)

    @staticmethod
    def deserialize(payload: str) -> list[dict]:
        return json.loads(payload)
