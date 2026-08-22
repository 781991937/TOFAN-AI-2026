# TOFAN AI 2026

مساعد تعليمي ذكي على Telegram يستقبل ملفات الدروس، يستخرج محتواها، ويعمل بنظام **Local-First**: معظم الشرح والاختبارات والتصحيح يعمل محليًا، بينما يتم استدعاء Google Gemini فقط عند طلب ميزة ذكية صريحة.

## المزايا

- استقبال PDF وDOCX وTXT من Telegram.
- استخراج النص وتنظيفه وتقسيمه.
- مكتبة دروس وأزرار مستقلة لكل درس.
- اختبار جديد وإعادة الاختبار.
- اختبار جماعي داخل المجموعات والقنوات.
- تصحيح تلقائي وحساب النسبة وشرح الأخطاء.
- المصطلحات الإنجليزية.
- حفظ الاختبارات والنتائج والتقدم.
- Gemini اختياري عند الحاجة فقط، مع إمكانية الاستفادة من التحليلات والاختبارات المخزنة بدل إعادة الطلب.
- PostgreSQL في الإنتاج، مع SQLite كخيار تطوير محلي.
- بنية Modular قابلة للتوسع.

## المتطلبات

- Python 3.11 أو أحدث.
- Telegram Bot Token من BotFather.
- Gemini API key من Google AI Studio.
- PostgreSQL للإنتاج طويل الأجل.

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

للتطوير المحلي يمكن ترك `DATABASE_URL` فارغًا، وسيستخدم المشروع SQLite.

للإنتاج يجب وضع رابط PostgreSQL:

```env
TELEGRAM_BOT_TOKEN=ضع_توكن_البوت_هنا
GEMINI_API_KEY=ضع_مفتاح_Gemini_هنا
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
MAX_FILE_SIZE_MB=20
```

**لا ترفع `.env` أو أي مفاتيح API إلى GitHub.**

## تشغيل البوت

```bash
python -m app.bot.main
```

## إعداد Render للإنتاج

1. أنشئ PostgreSQL Database دائمة في حساب الاستضافة.
2. خذ Internal/External Database URL حسب مكان الخدمة.
3. في Web Service افتح **Environment → Add Environment Variable**.
4. أضف:

```text
DATABASE_URL=رابط PostgreSQL
```

5. أعد Deploy للخدمة.
6. عند التشغيل سيختار `Database` PostgreSQL تلقائيًا عندما يكون `DATABASE_URL` موجودًا.

لا تضع رابط قاعدة البيانات داخل GitHub؛ ضعه في Environment Variables فقط.

## الاستخدام

1. افتح البوت واضغط `/start`.
2. أرسل PDF أو DOCX أو TXT.
3. يستخرج البوت النص ويحفظ بيانات الدرس.
4. تظهر مكتبة الدروس وأزرار الشرح والاختبار وإعادة الاختبار.
5. الاختبار العادي يعمل محليًا بدون Gemini.
6. عند الحاجة فقط استخدم زر الذكاء لشرح أعمق أو اختبار ذكي.

## الاختبار الجماعي

1. أضف البوت إلى المجموعة أو القناة بالصلاحيات المناسبة.
2. اختر الدرس ثم `👥 اختبار جماعي`.
3. يحصل كل مشارك على محاولة مستقلة لنفس الاختبار.
4. تحفظ النتائج وتظهر لوحة المتصدرين.

## الأوامر

- `/start` — تشغيل البوت.
- `/help` — المساعدة.
- `/lessons` — مكتبة الدروس.
- `/quiz` — اختبار آخر درس.
- `/summary` — شرح آخر درس.
- `/profile` — التقدم والإحصاءات.

## التصميم البرمجي

- `file_extractor.py`: استخراج PDF/DOCX/TXT.
- `ai_service.py`: Google Gemini للعمليات الذكية الصريحة.
- `quiz_generator.py`: إنشاء الاختبارات مع Local-First وCache.
- `database/db.py`: طبقة التخزين، PostgreSQL في الإنتاج وSQLite محليًا.
- `bot/handlers.py`: أوامر Telegram والملفات والدروس والاختبارات.
- `bot/keyboards.py`: أزرار Telegram.
- `config_gemini.py`: إعدادات البيئة.

## التخزين الدائم

بيانات المستخدمين والدروس والتحليلات والأسئلة والنتائج يجب أن تكون في PostgreSQL في الإنتاج. أما ملفات PDF/DOCX الأصلية الموجودة على قرص الخدمة فهي ليست تخزينًا دائمًا على الخطط المؤقتة؛ لذلك يعتمد التشغيل الدراسي على النص المستخرج المخزن في قاعدة البيانات، ويمكن لاحقًا إضافة Object Storage دائم للملفات الأصلية.

## ملاحظة مهمة

المشروع يستخدم Telegram polling حاليًا. موضوع منع السكون والاستضافة 24/7 يتم التعامل معه بعد تثبيت طبقة البيانات الدائمة.
