import hashlib
import json
import logging
import random
import sqlite3
from pathlib import Path

from .ai_service import AIService
from .local_engine import generate_local_questions

logger = logging.getLogger(__name__)


class QuizGenerator:
    """Local-first quiz generator. Gemini is used only when explicitly requested."""

    def __init__(self, ai_service: AIService, cache_path: Path | None = None):
        self.ai_service = ai_service
        self.cache_path = Path(cache_path) if cache_path else None
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS quiz_cache (cache_key TEXT PRIMARY KEY, mode TEXT NOT NULL, questions_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )

    @staticmethod
    def _key(text: str, count: int, difficulty: str, mode: str) -> str:
        raw = f"{mode}|{count}|{difficulty}|{text.strip()}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _fresh_variant(questions: list[dict]) -> list[dict]:
        """Create a genuinely different presentation without changing correctness."""
        result = []
        for q in questions:
            item = dict(q)
            options = list(item.get("options") or [])
            answer = str(item.get("answer", ""))
            if len(options) > 1:
                random.shuffle(options)
                item["options"] = options
                # answer stays as the option text, so correctness remains valid.
            result.append(item)
        random.shuffle(result)
        return result

    async def create(
        self,
        text: str,
        count: int = 10,
        difficulty: str = "medium",
        use_ai: bool = False,
        fresh: bool = False,
    ) -> list[dict]:
        if not text.strip():
            raise ValueError("Lesson text is empty")
        count = max(1, min(count, 50))
        mode = "ai" if use_ai else "local"
        key = self._key(text, count, difficulty, mode)

        if self.cache_path and not fresh:
            with sqlite3.connect(self.cache_path) as conn:
                row = conn.execute("SELECT questions_json FROM quiz_cache WHERE cache_key=?", (key,)).fetchone()
            if row:
                return json.loads(row[0])

        if use_ai:
            questions = await self.ai_service.generate_questions(text, count, difficulty)
        else:
            questions = generate_local_questions(text, count, difficulty)

        if not questions:
            raise RuntimeError("لم أستطع إنشاء أسئلة من محتوى الدرس")

        questions = self._fresh_variant(questions) if fresh else questions

        if self.cache_path and not fresh:
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO quiz_cache(cache_key,mode,questions_json) VALUES(?,?,?)",
                    (key, mode, json.dumps(questions, ensure_ascii=False)),
                )
        return questions

    async def create_smart(self, text: str, count: int = 10, difficulty: str = "medium") -> list[dict]:
        """Explicit AI mode with a local fallback so Gemini downtime never breaks quizzes."""
        try:
            return await self.create(text, count, difficulty, use_ai=True, fresh=True)
        except Exception as exc:
            logger.warning("Smart quiz Gemini failed; using local fallback: %s", exc)
            questions = generate_local_questions(text, min(count, 50), difficulty)
            if not questions:
                raise
            return self._fresh_variant(questions)

    @staticmethod
    def serialize(questions: list[dict]) -> str:
        return json.dumps(questions, ensure_ascii=False)

    @staticmethod
    def deserialize(payload: str) -> list[dict]:
        return json.loads(payload)
