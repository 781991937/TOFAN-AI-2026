import hashlib
import json
import random
import re
import sqlite3
from pathlib import Path

from .ai_service import AIService
from .local_engine import generate_local_questions


class QuizGenerator:
    """Two explicit engines: local Python for automation, Gemini for AI features."""

    def __init__(self, ai_service: AIService, cache_path: Path | None = None):
        self.ai_service = ai_service
        self.cache_path = Path(cache_path) if cache_path else None
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS quiz_cache (cache_key TEXT PRIMARY KEY, mode TEXT NOT NULL, questions_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    @staticmethod
    def _key(text: str, count: int, difficulty: str, mode: str, variant: str = "") -> str:
        raw = f"{mode}|{count}|{difficulty}|{variant}|{text.strip()}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def smart_count(text: str, requested: int = 20) -> int:
        requested = max(1, min(int(requested or 1), 50))
        if requested > 20:
            return requested
        clean = re.sub(r"\s+", " ", text or "").strip()
        words, chars = len(clean.split()), len(clean)
        if words < 120 or chars < 700: limit = 3
        elif words < 250 or chars < 1500: limit = 5
        elif words < 450 or chars < 2800: limit = 8
        elif words < 750 or chars < 5000: limit = 12
        else: limit = 20
        return min(requested, limit)

    @staticmethod
    def _fresh_variant(questions: list[dict]) -> list[dict]:
        result = []
        for question in questions:
            item = dict(question)
            options = list(item.get("options") or [])
            if len(options) > 1:
                random.shuffle(options)
                item["options"] = options
            result.append(item)
        random.shuffle(result)
        return result

    async def create_local(self, text: str, count: int = 10, difficulty: str = "medium") -> list[dict]:
        count = self.smart_count(text, count)
        questions = generate_local_questions(text, count, difficulty)
        if not questions:
            raise RuntimeError("لم أستطع إنشاء أسئلة من محتوى الملف")
        return self._fresh_variant(questions)

    async def create_smart(self, text: str, count: int = 20, difficulty: str = "medium") -> list[dict]:
        """AI-only quiz. Never falls back to the local engine."""
        if not text.strip():
            raise ValueError("Lesson text is empty")
        count = self.smart_count(text, count)
        variant = hashlib.sha1(f"{random.random()}".encode()).hexdigest()[:10]
        questions = await self.ai_service.generate_questions(text, count, difficulty, variant=variant)
        if not questions:
            raise RuntimeError("الذكاء الاصطناعي لم ينتج أسئلة كافية من المحتوى")
        return self._fresh_variant(questions)

    @staticmethod
    def serialize(questions: list[dict]) -> str:
        return json.dumps(questions, ensure_ascii=False)

    @staticmethod
    def deserialize(payload: str) -> list[dict]:
        return json.loads(payload)
