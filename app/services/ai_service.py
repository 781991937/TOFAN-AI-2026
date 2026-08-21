import json

from openai import AsyncOpenAI

from .file_extractor import chunk_text


class AIService:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def _json(self, messages: list[dict], temperature: float = 0.2) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=messages,
        )
        return json.loads(response.choices[0].message.content or "{}")

    async def analyze_lesson(self, text: str) -> dict:
        chunks = chunk_text(text, max_chars=12000)
        if not chunks:
            raise ValueError("Lesson text is empty")
        partials = []
        for chunk in chunks[:8]:
            partials.append(await self._json([
                {"role": "system", "content": "أنت مساعد تعليمي دقيق. أعد JSON صالحًا فقط."},
                {"role": "user", "content": "استخرج من هذا الجزء summary و concepts و key_points، بالعربية، وبدون معلومات خارج النص:\n" + chunk},
            ]))
        merged = json.dumps(partials, ensure_ascii=False)
        return await self._json([
            {"role": "system", "content": "أنت محرر تعليمي. أعد JSON صالحًا فقط بالمفاتيح summary و concepts و key_points. ادمج الأجزاء بدون تكرار ولا تضف معلومات خارجها."},
            {"role": "user", "content": "ادمج تحليلات أجزاء الدرس التالية:\n" + merged},
        ])

    async def generate_questions(self, text: str, count: int, difficulty: str) -> list[dict]:
        chunks = chunk_text(text, max_chars=12000)
        source = "\n\n".join(chunks[:8])
        prompt = f"""أنشئ {count} أسئلة اختبار من النص التالي، بمستوى صعوبة {difficulty}.
أعد JSON فقط بهذا الشكل: {{"questions":[{{"type":"mcq|true_false|short","question":"...","options":["..."] ,"answer":"...","explanation":"..."}}]}}
للـ true_false اجعل options ["صح","خطأ"]. ولـ mcq اجعل 3 أو 4 خيارات. ولـ short اجعل options []. اجعل الإجابة قابلة للتصحيح، واشرح الإجابة باختصار.
اعتمد على النص فقط ووزع الأسئلة على محتوى الدرس قدر الإمكان.

النص:
{source}"""
        data = await self._json([
            {"role": "system", "content": "أنت مولّد اختبارات تعليمية."},
            {"role": "user", "content": prompt},
        ], temperature=0.4)
        return data.get("questions", [])[:count]
