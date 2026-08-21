import json

from google import genai
from google.genai import types

from .file_extractor import chunk_text


class AIService:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def _json(self, prompt: str, temperature: float = 0.2) -> dict:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text or "{}")

    async def analyze_lesson(self, text: str) -> dict:
        chunks = chunk_text(text, max_chars=12000)
        if not chunks:
            raise ValueError("Lesson text is empty")

        partials = []
        for chunk in chunks[:8]:
            partials.append(await self._json(
                "أنت مساعد تعليمي دقيق. أعد JSON صالحًا فقط بالمفاتيح "
                "summary و concepts و key_points. حلل هذا الجزء بالعربية، "
                "ولا تضف معلومات خارج النص:\n\n" + chunk
            ))

        merged = json.dumps(partials, ensure_ascii=False)
        return await self._json(
            "أنت محرر تعليمي. أعد JSON صالحًا فقط بالمفاتيح summary و "
            "concepts و key_points. ادمج التحليلات التالية بدون تكرار، "
            "ولا تضف معلومات غير موجودة فيها:\n\n" + merged
        )

    async def generate_questions(self, text: str, count: int, difficulty: str) -> list[dict]:
        chunks = chunk_text(text, max_chars=12000)
        source = "\n\n".join(chunks[:8])
        prompt = f"""أنشئ {count} أسئلة اختبار من النص التالي، بمستوى صعوبة {difficulty}.
أعد JSON فقط بهذا الشكل:
{{"questions":[{{"type":"mcq|true_false|short","question":"...","options":["..."],"answer":"...","explanation":"..."}}]}}
للـ true_false اجعل options ["صح","خطأ"]. ولـ mcq اجعل 3 أو 4 خيارات. ولـ short اجعل options [].
اجعل الإجابة قابلة للتصحيح، واشرح الإجابة باختصار. اعتمد على النص فقط ووزع الأسئلة على محتوى الدرس قدر الإمكان.

النص:
{source}"""
        data = await self._json(prompt, temperature=0.4)
        return data.get("questions", [])[:count]
