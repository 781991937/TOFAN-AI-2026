import hashlib
import json
import sqlite3
from pathlib import Path

from .ai_service import AIService


class QuizGenerator:
    """Generate quizzes once and reuse identical quiz sets from SQLite."""

    def __init__(self, ai_service: AIService, cache_path: Path | None = None):
        self.ai_service = ai_service
        self.cache_path = Path(cache_path) if cache_path else None
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS ai_quiz_cache (cache_key TEXT PRIMARY KEY, model TEXT NOT NULL, questions_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    @staticmethod
    def _key(text: str, count: int, difficulty: str, model: str) -> str:
        raw = f"{model}|{count}|{difficulty}|{text.strip()}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    async def create(self, text: str, count: int = 10, difficulty: str = "medium") -> list[dict]:
        if not text.strip():
            raise ValueError("Lesson text is empty")
        count = max(1, min(count, 30))
        key = self._key(text, count, difficulty, self.ai_service.model)

        if self.cache_path:
            with sqlite3.connect(self.cache_path) as conn:
                row = conn.execute("SELECT questions_json FROM ai_quiz_cache WHERE cache_key=?", (key,)).fetchone()
            if row:
                return json.loads(row[0])

        questions = await self.ai_service.generate_questions(text, count, difficulty)
        if not questions:
            raise RuntimeError("AI did not return any questions")

        if self.cache_path:
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO ai_quiz_cache(cache_key,model,questions_json) VALUES(?,?,?)",
                    (key, self.ai_service.model, json.dumps(questions, ensure_ascii=False)),
                )
        return questions

    @staticmethod
    def serialize(questions: list[dict]) -> str:
        return json.dumps(questions, ensure_ascii=False)

    @staticmethod
    def deserialize(payload: str) -> list[dict]:
        return json.loads(payload)
