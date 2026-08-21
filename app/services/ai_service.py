import json
import logging

from google import genai
from google.genai import types

from .file_extractor import chunk_text

logger = logging.getLogger(__name__)


class AIService:
    """Gemini service optimized to minimize API calls.

    A lesson analysis is intentionally done in one request. Quiz generation is
    also one request and the caller caches its result in SQLite.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

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

        # One compact request instead of 8 partial requests + 1 merge request.
        # If the document is large, keep the first 10 chunks; this still costs
        # only one generation request and avoids quota explosions.
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
        return await self._json(prompt, temperature=0.15)

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
