from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

router = Router(name="sections")


@router.callback_query(F.data == "ai_section")
async def ai_section(callback: CallbackQuery) -> None:
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 اختيار ملف من المكتبة", callback_data="library")],
        [InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")],
    ])
    await callback.message.edit_text(
        "🧠 <b>قسم الذكاء الاصطناعي</b>\n\n"
        "هذا القسم مخصص للوظائف التي تستخدم الذكاء الاصطناعي فعلًا:\n\n"
        "• 🧠 شرح ذكي للمحتوى\n"
        "• 🧠 تحليل وفهم الدرس\n"
        "• 📝 توليد الاختبارات والأسئلة\n"
        "• 💡 تفسير الإجابات والأخطاء\n\n"
        "⚙️ أما استقبال الملفات وتقسيم الصفحات والتنقل والحفظ فهي من عمل نظام البوت، وليست من الذكاء الاصطناعي.",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "automation_section")
async def automation_section(callback: CallbackQuery) -> None:
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 المكتبة وإدارة الملفات", callback_data="library")],
        [InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")],
    ])
    await callback.message.edit_text(
        "⚙️ <b>قسم الأتمتة والبوت</b>\n\n"
        "هذا القسم مسؤول عن تشغيل وتنظيم الملفات بدون استدعاء الذكاء الاصطناعي:\n\n"
        "• 📥 استقبال PDF وDOCX وTXT\n"
        "• 📄 استخراج الصفحات وترتيبها\n"
        "• 🔢 أزرار الصفحات والتنقل\n"
        "• ⬅️ الملف السابق / التالي ➡️\n"
        "• 📥 إعادة تنزيل الملفات من Telegram\n"
        "• 📚 تصنيف المكتبة وترتيب المواد\n\n"
        "🧠 الذكاء الاصطناعي يُستدعى فقط عند اختيار وظيفة ذكية.",
        reply_markup=keyboard,
    )
