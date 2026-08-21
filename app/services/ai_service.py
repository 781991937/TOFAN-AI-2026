import hashlib
import json
import logging
import sqlite3
from pathlib import Path

from google import genai
from google.genai import types

from .file_extractor import chunk_text

logger = logging.getLogger(__name__)


class AIService:
    """Gemini service optimized to minimize API calls with SQLite caching."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", cache_path: Path | None = None):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.cache_path = Path(cache_path) if cache_path else None
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS ai_analysis_cache (content_hash TEXT PRIMARY KEY, model TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    async def _json(self, prompt: str, temperature: float = 0.2) -> dict:
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )
            return json.loads(response.text or "{}")
        except Exception as exc:
            logger.warning("Gemini request failed: %s", exc)
            raise

    async def analyze_lesson(self, text: str) -> dict:
        chunks = chunk_text(text, max_chars=9000)
        if not chunks:
            raise ValueError("Lesson text is empty")

        cache_key = self._hash(text)
        if self.cache_path:
            with sqlite3.connect(self.cache_path) as conn:
                row = conn.execute(
                    "SELECT result_json FROM ai_analysis_cache WHERE content_hash=? AND model=?",
                    (cache_key, self.model),
                ).fetchone()
            if row:
                logger.info("Gemini analysis cache hit: %s", cache_key[:12])
                return json.loads(row[0])

        # One compact request instead of 8 partial requests + 1 merge request.
        source = "\n\n--- جزء ---\n\n".join(chunks[:10])
        prompt = f"""أنت مساعد تعليمي دقيق. حلل الدرس التالي وأعد JSON صالحًا فقط بهذا الشكل:
{{
  "summary": "شرح عربي منظم ومختصر للدرس",
  "concepts": ["مفهوم مهم: تعريفه باختصار"],
  "key_points": ["نقطة أساسية 1", "نقطة أساسية 2"],
  "definitions": ["مصطلح: تعريفه"]
}}

التزم بمحتوى النص فقط، لا تخترع معلومات. اجعل الملخص واضحًا للطالب، واجعل القوائم مختصرة ومفيدة.

نص الدرس:
{source}"""
        result = await self._json(prompt, temperature=0.15)
        if self.cache_path:
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO ai_analysis_cache(content_hash,model,result_json) VALUES(?,?,?)",
                    (cache_key, self.model, json.dumps(result, ensure_ascii=False)),
                )
        return result

    async def generate_questions(self, text: str, count: int, difficulty: str) -> list[dict]:
        chunks = chunk_text(text, max_chars=9000)
        source = "\n\n--- جزء ---\n\n".join(chunks[:10])
        prompt = f"""أنشئ {count} أسئلة اختبار من النص التالي، بمستوى صعوبة {difficulty}.
أعد JSON فقط بهذا الشكل:
{{"questions":[{{"type":"mcq|true_false|short","question":"...","options":["..."],"answer":"...","explanation":"..."}}]}}
للـ true_false اجعل options ["صح","خطأ"]. ولـ mcq اجعل 3 أو 4 خيارات. ولـ short اجعل options [].
اجعل الإجابة قابلة للتصحيح، واشرح الإجابة باختصار. اعتمد على النص فقط ووزع الأسئلة على محتوى الدرس قدر الإمكان.

النص:
{source}"""
        data = await self._json(prompt, temperature=0.35)
        return data.get("questions", [])[:count]
