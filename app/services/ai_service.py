import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path

from google import genai
from google.genai import types

from .file_extractor import chunk_text


class AIService:
    """Explicit Gemini service used only by the AI section."""

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

    async def _json(self, prompt: str, temperature: float = 0.2, timeout: float = 25.0) -> dict:
        response = await asyncio.wait_for(
            self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=temperature, response_mime_type="application/json"),
            ), timeout=timeout,
        )
        data = json.loads(response.text or "{}")
        if not isinstance(data, dict):
            raise ValueError("Gemini returned invalid JSON")
        return data

    async def analyze_lesson(self, text: str) -> dict:
        chunks = chunk_text(text, max_chars=9000)
        if not chunks: raise ValueError("Lesson text is empty")
        key = self._hash(text)
        if self.cache_path:
            with sqlite3.connect(self.cache_path) as conn:
                row = conn.execute("SELECT result_json FROM ai_analysis_cache WHERE content_hash=? AND model=?", (key, self.model)).fetchone()
            if row: return json.loads(row[0])
        source = "\n\n--- جزء ---\n\n".join(chunks[:10])
        prompt = f"""أنت مدرس جامعي. اشرح المحتوى التالي بطريقة مختصرة وذكية تساعد على الاستيعاب.
أعد JSON فقط:
{{"summary":"شرح عربي منظم","concepts":["مفهوم"],"key_points":["نقطة"],"definitions":["تعريف"],"english_terms":["English Term — المعنى والشرح بالعربية"]}}
القواعد:
- التزم بالمحتوى فقط ولا تخترع.
- ضع كل مصطلح إنجليزي في السطر الأول ثم معناه وشرحه بالعربية في السطر الثاني عند عرضه لاحقًا.
- لا تخلط العربية داخل المصطلح الإنجليزي.
- لا تنسخ الأسطر المشوشة أو أرقام الصفحات.
النص:
{source}"""
        result = await self._json(prompt, temperature=0.15)
        if self.cache_path:
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute("INSERT OR REPLACE INTO ai_analysis_cache(content_hash,model,result_json) VALUES(?,?,?)", (key, self.model, json.dumps(result, ensure_ascii=False)))
        return result

    async def generate_questions(self, text: str, count: int, difficulty: str, variant: str = "") -> list[dict]:
        chunks = chunk_text(text, max_chars=9000)
        if not chunks: raise ValueError("Lesson text is empty")
        source = "\n\n--- جزء ---\n\n".join(chunks[:10])
        prompt = f"""أنشئ {count} سؤالًا متنوعًا من المحتوى التالي بمستوى {difficulty}.
هذا نموذج اختبار جديد رقم {variant}؛ لا تنسخ أسئلة نماذج سابقة إن كان بإمكانك صياغة نقاط مختلفة.
أعد JSON فقط: {{"questions":[{{"type":"mcq|true_false|short","question":"...","options":["..."],"answer":"...","explanation":"..."}}]}}
قواعد: mcq = 3 أو 4 خيارات، true_false = ["صح","خطأ"], short = []؛ اعتمد على النص فقط؛ وزع الأسئلة على أكبر قدر من المفاهيم؛ لا تستخدم أرقام الصفحات أو عنوان الملف كسؤال؛ لا تكرر السؤال نفسه؛ إذا كان المصطلح إنجليزيًا فضعه في سطر مستقل ثم العربي في السطر التالي.
المحتوى:
{source}"""
        data = await self._json(prompt, temperature=0.55, timeout=30.0)
        questions = data.get("questions", [])
        return questions[:count] if isinstance(questions, list) else []
