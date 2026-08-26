"""AI domain boundary.

AI-specific services are exposed here so Telegram handlers do not need to
know how the AI provider is constructed.
"""

from app.services import AIService, QuizGenerator


class AIEngine:
    def __init__(self, ai_service: AIService, quiz_generator: QuizGenerator) -> None:
        self.ai_service = ai_service
        self.quiz_generator = quiz_generator

    async def analyze(self, text: str) -> dict:
        return await self.ai_service.analyze_lesson(text)

    async def create_quiz(self, text: str, count: int, difficulty: str = "medium"):
        return await self.quiz_generator.create_smart(text, count, difficulty)

    async def create_local_quiz(self, text: str, count: int, difficulty: str = "medium"):
        return await self.quiz_generator.create_local(text, count, difficulty)
