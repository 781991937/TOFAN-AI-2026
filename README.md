# TOFAN AI 2026

مساعد تعليمي ذكي على Telegram يستقبل ملفات الدروس، يستخرج النص منها، يحلل المحتوى، وينشئ ملخصات واختبارات تفاعلية للطالب.

## المزايا

- استقبال PDF وDOCX وTXT من Telegram.
- استخراج النص وتنظيفه وتقسيمه إلى أجزاء.
- حفظ الدروس ونتائج الاختبارات في SQLite.
- تحليل الدروس باستخدام OpenAI.
- إنشاء ملخص ومفاهيم ونقاط رئيسية.
- إنشاء MCQ وTrue/False وShort Answer.
- اختبار تفاعلي داخل Telegram مع تصحيح وشرح للأخطاء.
- حفظ تقدم الطالب وإحصاءات النتائج.
- إعداد عدد الأسئلة ومستوى الصعوبة.
- بنية Modular قابلة لإضافة صيغ وخدمات أخرى لاحقًا.

## هيكل المشروع

```text
app/
  bot/
    handlers.py
    keyboards.py
    main.py
  database/
    db.py
  services/
    ai_service.py
    file_extractor.py
    quiz_generator.py
  config.py

data/
  uploads/
  processed/

tests/
requirements.txt
.env.example
.gitignore
README.md
```

## المتطلبات

- Python 3.11 أو أحدث.
- Telegram Bot Token من BotFather.
- OpenAI API key.

## التثبيت

```bash
git clone https://github.com/781991937/TOFAN-AI-2026.git
cd TOFAN-AI-2026
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

في Windows:

```powershell
.venv\Scripts\activate
```

## إعداد البيئة

انسخ `.env.example` إلى `.env`:

```bash
cp .env.example .env
```

ثم ضع القيم الخاصة بك:

```env
TELEGRAM_BOT_TOKEN=ضع_توكن_البوت_هنا
OPENAI_API_KEY=ضع_مفتاح_OpenAI_هنا
OPENAI_MODEL=gpt-4o-mini
MAX_FILE_SIZE_MB=20
```

**لا ترفع `.env` إلى GitHub.** وهو مستبعد بالفعل من `.gitignore`.

## تشغيل البوت

من جذر المشروع:

```bash
python -m app.bot.main
```

## الاستخدام

1. افتح البوت في Telegram واضغط `/start`.
2. أرسل ملف PDF أو DOCX أو TXT.
3. ينتظر البوت استخراج النص ثم تحليل المحتوى.
4. سيحفظ الدرس في SQLite ويعرض الملخص.
5. اضغط `إنشاء اختبار` أو استخدم `/quiz`.
6. أجب عن الأسئلة من أزرار Telegram، أو اكتب الإجابة عندما يكون السؤال قصيرًا.
7. في النهاية يعرض البوت النتيجة والنسبة ومراجعة الأخطاء مع الإجابة الصحيحة والشرح.

## الأوامر

- `/start` — تشغيل البوت.
- `/help` — عرض المساعدة.
- `/lessons` — عرض الدروس السابقة.
- `/quiz` — إنشاء اختبار من آخر درس.
- `/summary` — عرض ملخص آخر درس.
- `/profile` — عرض تقدم الطالب وإحصاءاته.

## التصميم البرمجي

- `file_extractor.py`: مسؤول عن PDF/DOCX/TXT والتنظيف والتقسيم.
- `ai_service.py`: مسؤول عن OpenAI وتحليل المحتوى وتوليد الأسئلة.
- `quiz_generator.py`: طبقة مستقلة لإنشاء الاختبارات وتخزينها بصيغة JSON.
- `database/db.py`: طبقة SQLite للمستخدمين والدروس والاختبارات والنتائج.
- `bot/handlers.py`: أوامر Telegram ومعالجة الملفات والاختبارات التفاعلية.

## ملاحظات

- يتم حفظ النص الكامل المستخرج من الملف في قاعدة البيانات، بينما تُقسّم نسخة المعالجة إلى أجزاء عند إرسالها إلى خدمة الذكاء الاصطناعي.
- النسخة الحالية تستخدم polling، ويمكن إضافة webhook لاحقًا.
- يمكن إضافة OCR للملفات المصورة، وصيغ PowerPoint، وحسابات متعددة، ولوحة إدارة في إصدارات لاحقة.
