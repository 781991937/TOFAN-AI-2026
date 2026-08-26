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
from app.services.file_extractor import page_parts

logger=logging.getLogger(__name__); router=Router(name="sections")

def key(l): return str(l["file_id"] or l["file_path"] or l["file_name"])
def title(l):
    n=str(l["file_name"] or "الدرس"); return n.split(" - ",1)[1] if " - " in n else n
def pos(l,items):
    group=file_lessons(items,key(l))
    return next((i for i,x in enumerate(group,1) if int(x["id"])==int(l["id"])),1),len(group)
def qcount(text):
    w=len(str(text or "").split()); c=len(str(text or ""))
    if w<120 or c<700:return 3
    if w<250 or c<1500:return 5
    if w<450 or c<2800:return 8
    if w<750 or c<5000:return 12
    return 20
def term_text(data):
    blocks=[]
    for x in (data.get("english_terms") or [])[:10]:
        raw=str(x); en,ar=raw.split(" — ",1) if " — " in raw else (raw,"ترجمة وشرح عربي من المحتوى")
        blocks.append(f"<b>{html.escape(en.strip())}</b>\n{html.escape(ar.strip())}")
    return "\n\n".join(blocks) or "لا توجد مصطلحات واضحة."
def page_kb(lid,pages,i):
    from aiogram.types import InlineKeyboardButton,InlineKeyboardMarkup
    rows=[]
    for s in range(0,len(pages),6): rows.append([InlineKeyboardButton(text=("🔵" if j==i else "📄")+f" {pages[j][0]}",callback_data=f"ai_page:{lid}:{j}") for j in range(s,min(s+6,len(pages)))])
    nav=[]
    if i>0: nav.append(InlineKeyboardButton(text="⬅️ السابقة",callback_data=f"ai_page:{lid}:{i-1}"))
    if i<len(pages)-1: nav.append(InlineKeyboardButton(text="التالية ➡️",callback_data=f"ai_page:{lid}:{i+1}"))
    if nav: rows.append(nav)
    rows += [[InlineKeyboardButton(text="🧠 شرح هذه الصفحة",callback_data=f"ai_page_explain:{lid}:{i}")],[InlineKeyboardButton(text="📝 اختبار هذه الصفحة",callback_data=f"ai_page_quiz:{lid}:{i}")],[InlineKeyboardButton(text="⬅️ قائمة الدرس",callback_data=f"ai_lessonback:{lid}")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)
def page_view(l,pages,i):
    n,body=pages[i]
    return (f"📖 <b>{html.escape(title(l))}</b>\n🔢 <b>صفحة {n} من {len(pages)}</b>\n📚 <b>القسم:</b> {html.escape(str(l['category'] or '📂 مواد أخرى'))}\n\n⚙️ <b>طريقة العرض: البوت والأتمتة — Python</b>\n🧠 <b>طريقة الشرح والاختبار: الذكاء الاصطناعي</b>\n\n📄 <b>محتوى الصفحة</b>\n{html.escape(body[:3000])}")[:3900]

@router.callback_query(F.data=="ai_section")
async def ai_section(c:CallbackQuery): await c.answer(); await c.message.edit_text("🧠 <b>قسم الذكاء الاصطناعي</b>\n\n📚 القسم ← الملف ← الدرس ← الصفحة.\n⚙️ التنظيم والتنقل والصفحات بواسطة Python.\n🧠 الشرح والاختبارات بواسطة الذكاء الاصطناعي فقط.",reply_markup=section_menu("ai"))

@router.callback_query(F.data=="ai_library")
async def ai_library(c:CallbackQuery,db:Database):
    cats=prepare_categories(db,c.from_user.id); await c.answer()
    if not cats: await c.message.edit_text("📚 <b>المكتبة فارغة</b>\n\nأرسل ملفًا أولًا.",reply_markup=section_menu("ai")); return
    await c.message.edit_text("🧠 <b>مكتبة الذكاء الاصطناعي</b>\n\nاختر القسم:",reply_markup=ai_categories_menu(cats))

@router.callback_query(F.data.startswith("ai_category:"))
async def ai_category(c:CallbackQuery,db:Database):
    cats=prepare_categories(db,c.from_user.id); value=c.data.split(":",1)[1]; cat=next((str(x["category"]) for x in cats if token(str(x["category"]))==value),None); await c.answer()
    if not cat: await c.message.edit_text("❌ القسم غير موجود."); return
    await c.message.edit_text(f"🧠 <b>{html.escape(cat)}</b>\n\nاختر:",reply_markup=ai_category_menu(cat))

@router.callback_query(F.data.startswith("ai_categoryfiles:"))
async def ai_categoryfiles(c:CallbackQuery,db:Database):
    cats=prepare_categories(db,c.from_user.id); cat=next((str(x["category"]) for x in cats if token(str(x["category"]))==c.data.split(":",1)[1]),None); await c.answer()
    if not cat: await c.message.edit_text("❌ القسم غير موجود."); return
    ls=db.get_lessons_by_category(c.from_user.id,cat); await c.message.edit_text(f"📚 <b>{html.escape(cat)}</b>\n\nاختر الملف:",reply_markup=ai_files_menu(files_in_category(ls),cat))

@router.callback_query(F.data.startswith("ai_file:"))
async def ai_file(c:CallbackQuery,db:Database):
    ls=db.get_lessons(c.from_user.id,1000); k=find_file(ls,c.data.split(":",1)[1]); await c.answer()
    if not k: await c.message.edit_text("❌ الملف غير موجود."); return
    selected=file_lessons(ls,k); await c.message.edit_text(f"🧠 <b>قسم الذكاء الاصطناعي</b>\n📚 <b>{html.escape(str(selected[0]['category'] or '📂 مواد أخرى'))}</b>\n📘 <b>{html.escape(str(selected[0]['file_name']))}</b>\n\nاختر الدرس:",reply_markup=ai_lessons_menu(selected,k))

@router.callback_query(F.data.startswith("ai_fileback:"))
async def ai_fileback(c:CallbackQuery,db:Database):
    ls=db.get_lessons(c.from_user.id,1000); k=find_file(ls,c.data.split(":",1)[1]); await c.answer()
    if not k: await c.message.edit_text("❌ الملف غير موجود."); return
    selected=file_lessons(ls,k); cat=str(selected[0]["category"] or "📂 مواد أخرى"); await c.message.edit_text(f"📚 <b>{html.escape(cat)}</b>\n\nاختر الملف:",reply_markup=ai_files_menu(files_in_category(db.get_lessons_by_category(c.from_user.id,cat)),cat))

@router.callback_query(F.data.startswith("ai_lesson:"))
async def ai_lesson(c:CallbackQuery,db:Database):
    _,lid,_=c.data.split(":",2); l=db.get_lesson(int(lid),c.from_user.id); await c.answer()
    if not l: await c.message.edit_text("❌ الدرس غير موجود."); return
    n,total=pos(l,db.get_lessons(c.from_user.id,1000)); await c.message.edit_text(f"📖 <b>{html.escape(title(l))}</b>\n🔢 <b>الدرس {n} من {total}</b>\n📚 <b>القسم:</b> {html.escape(str(l['category'] or '📂 مواد أخرى'))}\n\n🧠 <b>طريقة الشرح والاختبار: الذكاء الاصطناعي</b>",reply_markup=ai_lesson_menu(int(lid),key(l)))

@router.callback_query(F.data.startswith("ai_lessonback:"))
async def ai_lessonback(c:CallbackQuery,db:Database):
    l=db.get_lesson(int(c.data.split(":",1)[1]),c.from_user.id); await c.answer()
    if not l: await c.message.edit_text("❌ الدرس غير موجود."); return
    k=key(l); selected=file_lessons(db.get_lessons(c.from_user.id,1000),k); await c.message.edit_text(f"📘 <b>{html.escape(str(l['file_name']))}</b>\n\nاختر الدرس:",reply_markup=ai_lessons_menu(selected,k))

@router.callback_query(F.data.startswith("ai_explain:"))
async def ai_explain(c:CallbackQuery,db:Database,ai_service:AIService):
    l=db.get_lesson(int(c.data.split(":",1)[1]),c.from_user.id)
    if not l: await c.answer("❌ الدرس غير موجود.",show_alert=True); return
    await c.answer("🧠 جاري الشرح…")
    try:
        a=await ai_service.analyze_lesson(str(l["extracted_text"] or "")); terms=term_text(a); summary=html.escape(str(a.get("summary") or "لا يوجد شرح كافٍ."))
        await c.message.edit_text(f"📖 <b>{html.escape(title(l))}</b>\n📚 <b>القسم:</b> {html.escape(str(l['category'] or '📂 مواد أخرى'))}\n\n🧠 <b>طريقة الشرح: الذكاء الاصطناعي</b>\n\n{summary}\n\n🇬🇧 <b>English Terms</b>\n{terms}",reply_markup=ai_lesson_menu(int(l["id"]),key(l)))
    except Exception: await c.message.edit_text("⚠️ تعذر تشغيل الذكاء الاصطناعي. الملف محفوظ.")

@router.callback_query(F.data.startswith("ai_quiz:"))
async def ai_quiz(c:CallbackQuery,state:FSMContext,db:Database,quiz_generator:QuizGenerator):
    l=db.get_lesson(int(c.data.split(":",1)[1]),c.from_user.id)
    if not l: await c.answer("❌ الدرس غير موجود.",show_alert=True); return
    await c.answer("🧠 جاري إنشاء اختبار جديد…")
    try:
        qs=await quiz_generator.create_smart(str(l["extracted_text"] or ""),qcount(str(l["extracted_text"] or "")),"medium")
        qid=db.create_quiz(int(l["id"]),quiz_generator.serialize(qs),len(qs),"medium"); await state.set_state(QuizState.active); await state.update_data(quiz_id=qid,lesson_id=int(l["id"]),questions=qs,answers=[],group_mode=False)
        await c.message.edit_text(f"📝 <b>اختبار الدرس</b>\n🧠 <b>الذكاء الاصطناعي</b>\n🎯 {len(qs)} أسئلة حسب حجم المحتوى."); await send_question(c.message,state,qid,qs,0,[],db)
    except Exception: await c.message.edit_text("⚠️ تعذر إنشاء الاختبار بالذكاء الاصطناعي. لم أستخدم المحرك المحلي.")

@router.callback_query(F.data.startswith("ai_page:"))
async def ai_page(c:CallbackQuery,db:Database):
    _,lid,idx=c.data.split(":"); l=db.get_lesson(int(lid),c.from_user.id); await c.answer()
    if not l: await c.message.edit_text("❌ الدرس غير موجود."); return
    pages=page_parts(str(l["extracted_text"] or "")); i=int(idx)
    if not pages or i<0 or i>=len(pages): await c.answer("❌ الصفحة غير موجودة.",show_alert=True); return
    await c.message.edit_text(page_view(l,pages,i),reply_markup=page_keyboard(int(lid),pages,i))

@router.callback_query(F.data.startswith("ai_page_explain:"))
async def ai_page_explain(c:CallbackQuery,db:Database,ai_service:AIService):
    _,lid,idx=c.data.split(":"); l=db.get_lesson(int(lid),c.from_user.id); pages=page_parts(str(l["extracted_text"] or "")) if l else []; i=int(idx)
    if not l or not pages or i>=len(pages): await c.answer("❌ الصفحة غير موجودة.",show_alert=True); return
    await c.answer("🧠 جاري شرح الصفحة…")
    try:
        a=await ai_service.analyze_lesson(pages[i][1]); await c.message.edit_text(f"📖 <b>{html.escape(title(l))}</b>\n🔢 <b>صفحة {pages[i][0]} من {len(pages)}</b>\n\n🧠 <b>طريقة الشرح: الذكاء الاصطناعي</b>\n\n{html.escape(str(a.get('summary') or 'لا يوجد شرح كافٍ.'))}",reply_markup=page_keyboard(int(lid),pages,i))
    except Exception: await c.answer("❌ تعذر شرح الصفحة.",show_alert=True)

@router.callback_query(F.data.startswith("ai_page_quiz:"))
async def ai_page_quiz(c:CallbackQuery,state:FSMContext,db:Database,quiz_generator:QuizGenerator):
    _,lid,idx=c.data.split(":"); l=db.get_lesson(int(lid),c.from_user.id); pages=page_parts(str(l["extracted_text"] or "")) if l else []; i=int(idx)
    if not l or not pages or i>=len(pages): await c.answer("❌ الصفحة غير موجودة.",show_alert=True); return
    await c.answer("🧠 جاري إنشاء اختبار الصفحة…")
    try:
        qs=await quiz_generator.create_smart(pages[i][1],min(10,qcount(pages[i][1])),"medium"); qid=db.create_quiz(int(lid),quiz_generator.serialize(qs),len(qs),"medium"); await state.set_state(QuizState.active); await state.update_data(quiz_id=qid,lesson_id=int(lid),questions=qs,answers=[],group_mode=False); await c.message.edit_text(f"📝 <b>اختبار صفحة {pages[i][0]}</b>\n🧠 <b>الذكاء الاصطناعي فقط</b>"); await send_question(c.message,state,qid,qs,0,[],db)
    except Exception: await c.message.edit_text("⚠️ تعذر إنشاء اختبار الصفحة.")

@router.callback_query(F.data=="bot_section")
async def bot_section(c:CallbackQuery): await c.answer(); await c.message.edit_text("🤖 <b>قسم البوت والأتمتة</b>\n\n📚 القسم ← الملف ← الدرس.\n⚙️ الاستقبال والتصنيف والتقسيم والحفظ والتنزيل والصفحات والتنقل بواسطة Python فقط.\n\n🧠 لا توجد هنا وظائف ذكاء اصطناعي.",reply_markup=section_menu("bot"))

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
async def help_button(c:CallbackQuery): await c.answer(); await c.message.edit_text("❓ <b>المساعدة</b>\n\nأرسل الملف ← البوت يصنفه ويحفظه ← القسم ← الملف ← الدرس.\n\n🧠 قسم الذكاء: الشرح والاختبارات بالذكاء الاصطناعي.\n🤖 قسم البوت: الأتمتة والصفحات والتنزيل بواسطة Python.",reply_markup=main_menu())
