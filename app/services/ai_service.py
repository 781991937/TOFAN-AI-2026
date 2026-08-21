import json
from openai import AsyncOpenAI


class AIService:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def analyze_lesson(self, text: str) -> dict:
        prompt = """حلّل محتوى الدرس التالي للطالب. أعد JSON صالحًا فقط بالمفاتيح:
summary (ملخص منظم)، concepts (قائمة أهم المفاهيم والتعريفات)، key_points (قائمة نقاط مهمة).
اكتب بالعربية بوضوح، ولا تضف معلومات غير موجودة في النص.

النص:
""" + text
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "أنت مساعد تعليمي دقيق."},
                {"role": "user", "content": prompt},
            ],
        )
        return json.loads(response.choices[0].message.content or "{}")

    async def generate_questions(self, text: str, count: int, difficulty: str) -> list[dict]:
        prompt = f"""أنشئ {count} أسئلة اختبار من النص التالي، بمستوى صعوبة {difficulty}.
أعد JSON فقط بهذا الشكل: {{"questions":[{{"type":"mcq|true_false|short","question":"...","options":["..."] ,"answer":"...","explanation":"..."}}]}}
للـ true_false اجعل options ["صح","خطأ"]. ولـ short اجعل options []. الإجابة يجب أن تكون قابلة للتصحيح.
اعتمد على النص فقط.

النص:
{text}"""
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.4,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "أنت مولّد اختبارات تعليمية."},
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(response.choices[0].message.content or "{}")
        return data.get("questions", [])[:count]
