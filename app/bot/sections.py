import html
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from app.bot.keyboards import ai_categories_menu, ai_category_menu, ai_files_menu, ai_lessons_menu, ai_lesson_menu, section_menu, settings_menu, count_menu, difficulty_menu, main_menu
from app.bot.library import prepare_categories, files_in_category, find_file, file_lessons, token
from app.bot.quiz_engine import QuizState, send_question
from app.database import Database
from app.services import AIService, QuizGenerator

logger=logging.getLogger(__name__)
router=Router(name="sections")

def lesson_key(l): return str(l["file_id"] or l["file_path"] or l["file_name"])
def lesson_title(l):
    n=str(l["file_name"] or "الدرس"); return n.split(" - ",1)[1] if " - " in n else n

def position(l, all_lessons):
    group=file_lessons(all_lessons,lesson_key(l))
    for i,x in enumerate(group,1):
        if int(x["id"])==int(l["id"]): return i,len(group)
    return 1,len(group)

def adaptive_count(text):
    words=len(str(text or "").split()); chars=len(str(text or ""))
    if words<120 or chars<700:return 3
    if words<250 or chars<1500:return 5
    if words<450 or chars<2800:return 8
    if words<750 or chars<5000:return 12
    return 20

def page_keyboard(lesson_id,pages,index):
    from aiogram.types import InlineKeyboardButton,InlineKeyboardMarkup
    rows=[]
    for start in range(0,len(pages),6):
        rows.append([InlineKeyboardButton(text=("🔵" if i==index else "📄")+f" {pages[i][0]}",callback_data=f"ai_page:{lesson_id}:{i}") for i in range(start,min(start+6,len(pages)))])
    nav=[]
    if index>0:nav.append(InlineKeyboardButton(text="⬅️ السابقة",callback_data=f"ai_page:{lesson_id}:{index-1}"))
    if index<len(pages)-1:nav.append(InlineKeyboardButton(text="التالية ➡️",callback_data=f"ai_page:{lesson_id}:{index+1}"))
    if nav:rows.append(nav)
    rows += [[InlineKeyboardButton(text="🧠 شرح هذه الصفحة",callback_data=f"ai_page_explain:{lesson_id}:{index}")],[InlineKeyboardButton(text="📝 اختبار هذه الصفحة",callback_data=f"ai_page_quiz:{lesson_id}:{index}")],[InlineKeyboardButton(text="⬅️ قائمة الدرس",callback_data=f"ai_lessonback:{lesson_id}")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def page_text(lesson,pages,index):
    n,body=pages[index]
    return (f"📖 <b>{html.escape(lesson_title(lesson))}</b>\n🔢 <b>صفحة {n} من {len(pages)}</b>\n📚 <b>القسم:</b> {html.escape(str(lesson['category'] or '📂 مواد أخرى'))}\n\n⚙️ <b>طريقة العرض: البوت والأتمتة — Python</b>\n🧠 <b>طريقة الشرح والاختبار: الذكاء الاصطناعي</b>\n\n📄 <b>محتوى الصفحة</b>\n{html.escape(body[:3000])}")[:3900]

@router.callback_query(F.data=="ai_section")
async def ai_section(c:CallbackQuery):
    await c.answer(); await c.message.edit_text("🧠 <b>قسم الذكاء الاصطناعي</b>\n\n📚 القسم ← الملف ← الدرس ← الصفحة.\n⚙️ التنظيم والتنقل والصفحات بواسطة Python.\n🧠 الشرح والاختبارات بواسطة الذكاء الاصطناعي فقط.",reply_markup=section_menu("ai"))

@router.callback_query(F.data=="ai_library")
async def ai_library(c:CallbackQuery,db:Database):
    cats=prepare_categories(db,c.from_user.id); await c.answer()
    if not cats: await c.message.edit_text("📚 <b>المكتبة فارغة</b>\n\nأرسل ملفًا أولًا.",reply_markup=section_menu("ai")); return
    await c.message.edit_text("🧠 <b>مكتبة الذكاء الاصطناعي</b>\n\nاختر القسم:",reply_markup=ai_categories_menu(cats))

@router.callback_query(F.data.startswith("ai_category:"))
async def ai_category(c:CallbackQuery,db:Database):
    cats=prepare_categories(db,c.from_user.id); value=c.data.split(":",1)[1]; cat=next((str(x["category"]) for x in cats if token(str(x["category"]))==value),None); await c.answer()
    if not cat: await c.message.edit_text("❌ القسم غير موجود.",reply_markup=section_menu("ai")); return
    await c.message.edit_text(f"🧠 <b>{html.escape(cat)}</b>\n\nاختر:",reply_markup=ai_category_menu(cat))

@router.callback_query(F.data.startswith("ai_categoryfiles:"))
async def ai_categoryfiles(c:CallbackQuery,db:Database):
    cats=prepare_categories(db,c.from_user.id); cat=next((str(x["category"]) for x in cats if token(str(x["category"]))==c.data.split(":",1)[1]),None); await c.answer()
    if not cat: await c.message.edit_text("❌ القسم غير موجود."); return
    lessons=db.get_lessons_by_category(c.from_user.id,cat); await c.message.edit_text(f"📚 <b>{html.escape(cat)}</b>\n\nاختر الملف:",reply_markup=ai_files_menu(files_in_category(lessons),cat))

@router.callback_query(F.data.startswith("ai_file:"))
async def ai_file(c:CallbackQuery,db:Database):
    all_lessons=db.get_lessons(c.from_user.id,1000); key=find_file(all_lessons,c.data.split(":",1)[1]); await c.answer()
    if not key: await c.message.edit_text("❌ الملف غير موجود."); return
    selected=file_lessons(all_lessons,key); await c.message.edit_text(f"🧠 <b>قسم الذكاء الاصطناعي</b>\n📚 <b>{html.escape(str(selected[0]['category'] or '📂 مواد أخرى'))}</b>\n📘 <b>{html.escape(str(selected[0]['file_name']))}</b>\n\nاختر الدرس:",reply_markup=ai_lessons_menu(selected,key))

@router.callback_query(F.data.startswith("ai_fileback:"))
async def ai_fileback(c:CallbackQuery,db:Database):
    all_lessons=db.get_lessons(c.from_user.id,1000); key=find_file(all_lessons,c.data.split(":",1)[1]); await c.answer()
    if not key: await c.message.edit_text("❌ الملف غير موجود."); return
    selected=file_lessons(all_lessons,key); cat=str(selected[0]["category"] or "📂 مواد أخرى"); await c.message.edit_text(f"📚 <b>{html.escape(cat)}</b>\n\nاختر الملف:",reply_markup=ai_files_menu(files_in_category(db.get_lessons_by_category(c.from_user.id,cat)),cat))

@router.callback_query(F.data.startswith("ai_lesson:"))
async def ai_lesson(c:CallbackQuery,db:Database):
    _,lid,_=c.data.split(":",2); l=db.get_lesson(int(lid),c.from_user.id); await c.answer()
    if not l: await c.message.edit_text("❌ الدرس غير موجود."); return
    n,total=position(l,db.get_lessons(c.from_user.id,1000)); await c.message.edit_text(f"📖 <b>{html.escape(lesson_title(l))}</b>\n🔢 <b>الدرس {n} من {total}</b>\n📚 <b>القسم:</b> {html.escape(str(l['category'] or '📂 مواد أخرى'))}\n\n🧠 <b>طريقة الشرح والاختبار: الذكاء الاصطناعي</b>",reply_markup=ai_lesson_menu(int(lid),lesson_key(l)))

@router.callback_query(F.data.startswith("ai_lessonback:"))
async def ai_lessonback(c:CallbackQuery,db:Database):
    l=db.get_lesson(int(c.data.split(":",1)[1]),c.from_user.id); await c.answer()
    if not l: await c.message.edit_text("❌ الدرس غير موجود."); return
    key=lesson_key(l); selected=file_lessons(db.get_lessons(c.from_user.id,1000),key); await c.message.edit_text(f"📘 <b>{html.escape(str(l['file_name']))}</b>\n\nاختر الدرس:",reply_markup=ai_lessons_menu(selected,key))

@router.callback_query(F.data.startswith("ai_explain:"))
async def ai_explain(c:CallbackQuery,db:Database,ai_service:AIService):
    l=db.get_lesson(int(c.data.split(":",1)[1]),c.from_user.id)
    if not l: await c.answer("❌ الدرس غير موجود.",show_alert=True); return
    await c.answer("🧠 جاري الشرح…")
    try:
        a=await ai_service.analyze_lesson(str(l["extracted_text"] or "")); terms=a.get("english_terms") or []; blocks=[]
        for x in terms[:10]:
            raw=str(x); en,ar=raw.split(" — ",1) if " — " in raw else (raw,"ترجمة وشرح عربي من المحتوى"); blocks.append(f"<b>{html.escape(en.strip())}</b>\n{html.escape(ar.strip())}")
        await c.message.edit_text(f"📖 <b>{html.escape(lesson_title(l))}</b>\n📚 <b>القسم:</b> {html.escape(str(l['category'] or '📂 مواد أخرى'))}\n\n🧠 <b>طريقة الشرح: الذكاء الاصطناعي</b>\n\n{html.escape(str(a.get('summary') or 'لا يوجد شرح كافٍ.'))}\n\n🇬🇧 <b>English Terms</b>\n{'\n\n'.join(blocks) or 'لا توجد مصطلحات واضحة.'}",reply_markup=ai_lesson_menu(int(l["id"]),lesson_key(l)))
    except Exception: await c.message.edit_text("⚠️ تعذر تشغيل الذكاء الاصطناعي. الملف محفوظ.")

@router.callback_query(F.data.startswith("ai_quiz:"))
async def ai_quiz(c:CallbackQuery,state:FSMContext,db:Database,quiz_generator:QuizGenerator):
    l=db.get_lesson(int(c.data.split(":",1)[1]),c.from_user.id)
    if not l: await c.answer("❌ الدرس غير موجود.",show_alert=True); return
    await c.answer("🧠 جاري إنشاء اختبار جديد…")
    try:
        count=adaptive_count(str(l["extracted_text"] or "")); qs=await quiz_generator.create_smart(str(l["extracted_text"] or ""),count,"medium"); qid=db.create_quiz(int(l["id"]),quiz_generator.serialize(qs),len(qs),"medium")
        await state.set_state(QuizState.active); await state.update_data(quiz_id=qid,lesson_id=int(l["id"]),questions=qs,answers=[],group_mode=False); await c.message.edit_text(f"📝 <b>اختبار الدرس</b>\n🧠 <b>الذكاء الاصطناعي</b>\n🎯 {len(qs)} أسئلة حسب حجم المحتوى."); await send_question(c.message,state,qid,qs,0,[],db)
    except Exception: await c.message.edit_text("⚠️ تعذر إنشاء الاختبار بالذكاء الاصطناعي. لم أستخدم المحرك المحلي.")

@router.callback_query(F.data.startswith("ai_page:"))
async def ai_page(c:CallbackQuery,db:Database):
    _,lid,idx=c.data.split(":"); l=db.get_lesson(int(lid),c.from_user.id); await c.answer()
    if not l: await c.message.edit_text("❌ الدرس غير موجود."); return
    pages=page_parts(str(l["extracted_text"] or "")); i=int(idx)
    if not pages or i<0 or i>=len(pages): await c.answer("❌ الصفحة غير موجودة.",show_alert=True); return
    await c.message.edit_text(page_text(l,pages,i),reply_markup=page_keyboard(int(lid),pages,i))

@router.callback_query(F.data.startswith("ai_page_explain:"))
async def ai_page_explain(c:CallbackQuery,db:Database,ai_service:AIService):
    _,lid,idx=c.data.split(":"); l=db.get_lesson(int(lid),c.from_user.id); pages=page_parts(str(l["extracted_text"] or "")) if l else []; i=int(idx)
    if not l or not pages or i>=len(pages): await c.answer("❌ الصفحة غير موجودة.",show_alert=True); return
    await c.answer("🧠 جاري الشرح…")
    try:
        a=await ai_service.analyze_lesson(pages[i][1]); await c.message.edit_text(f"📖 <b>{html.escape(lesson_title(l))}</b>\n🔢 <b>صفحة {pages[i][0]} من {len(pages)}</b>\n\n🧠 <b>طريقة الشرح: الذكاء الاصطناعي</b>\n\n{html.escape(str(a.get('summary') or 'لا يوجد شرح كافٍ.'))}",reply_markup=page_keyboard(int(lid),pages,i))
    except Exception: await c.answer("❌ تعذر شرح الصفحة.",show_alert=True)

@router.callback_query(F.data.startswith("ai_page_quiz:"))
async def ai_page_quiz(c:CallbackQuery,state:FSMContext,db:Database,quiz_generator:QuizGenerator):
    _,lid,idx=c.data.split(":"); l=db.get_lesson(int(lid),c.from_user.id); pages=page_parts(str(l["extracted_text"] or "")) if l else []; i=int(idx)
    if not l or not pages or i>=len(pages): await c.answer("❌ الصفحة غير موجودة.",show_alert=True); return
    await c.answer("🧠 جاري إنشاء اختبار الصفحة…")
    try:
        qs=await quiz_generator.create_smart(pages[i][1],min(10,adaptive_count(pages[i][1])),"medium"); qid=db.create_quiz(int(lid),quiz_generator.serialize(qs),len(qs),"medium"); await state.set_state(QuizState.active); await state.update_data(quiz_id=qid,lesson_id=int(lid),questions=qs,answers=[],group_mode=False); await c.message.edit_text(f"📝 <b>اختبار صفحة {pages[i][0]}</b>\n🧠 <b>الذكاء الاصطناعي فقط</b>"); await send_question(c.message,state,qid,qs,0,[],db)
    except Exception: await c.message.edit_text("⚠️ تعذر إنشاء اختبار الصفحة.")

@router.callback_query(F.data=="bot_section")
async def bot_section(c:CallbackQuery):
    await c.answer(); await c.message.edit_text("🤖 <b>قسم البوت والأتمتة</b>\n\n📚 القسم ← الملف ← الدرس.\n⚙️ استقبال وتصنيف وتقسيم وحفظ وتنزيل وصفحات وتنقل بواسطة Python فقط.\n\n🧠 لا توجد هنا وظائف ذكاء اصطناعي.",reply_markup=section_menu("bot"))

@router.callback_query(F.data=="settings")
async def settings(c:CallbackQuery,db:Database):
    db.ensure_user(c.from_user.id,c.from_user.first_name or ""); u=db.get_user(c.from_user.id); await c.answer(); await c.message.edit_text("⚙️ <b>إعدادات البوت</b>",reply_markup=settings_menu(u["question_count"],u["difficulty"]))
@router.callback_query(F.data=="set_count")
async def set_count(c:CallbackQuery): await c.answer(); await c.message.edit_text("اختر العدد:",reply_markup=count_menu())
@router.callback_query(F.data.startswith("count:"))
async def set_count_value(c:CallbackQuery,db:Database):
    u=db.get_user(c.from_user.id); db.update_settings(c.from_user.id,int(c.data.split(":")[1]),u["difficulty"]); await c.answer("تم الحفظ ✅"); await settings(c,db)
@router.callback_query(F.data=="set_difficulty")
async def set_difficulty(c:CallbackQuery): await c.answer(); await c.message.edit_text("اختر الصعوبة:",reply_markup=difficulty_menu())
@router.callback_query(F.data.startswith("difficulty:"))
async def set_difficulty_value(c:CallbackQuery,db:Database):
    u=db.get_user(c.from_user.id); db.update_settings(c.from_user.id,u["question_count"],c.data.split(":",1)[1]); await c.answer("تم الحفظ ✅"); await settings(c,db)
@router.callback_query(F.data=="help")
async def help_button(c:CallbackQuery):
    await c.answer(); await c.message.edit_text("❓ <b>المساعدة</b>\n\nأرسل الملف ← البوت يصنفه ويحفظه ← القسم ← الملف ← الدرس.\n\n🧠 قسم الذكاء: الشرح والاختبارات بالذكاء الاصطناعي.\n🤖 قسم البوت: الأتمتة والصفحات والتنزيل بواسطة Python.",reply_markup=main_menu())
