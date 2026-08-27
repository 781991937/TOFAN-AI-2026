"""AI-only page formatting helpers."""

import html


def ai_page_text(lesson, pages, index: int) -> str:
    number, body = pages[index]
    title = html.escape(str(lesson["file_name"] or "الدرس").split(" - ", 1)[-1])
    body = str(body or "").strip()
    return (
        f"🧠 <b>{title}</b>\n"
        f"📄 <b>الصفحة {number} من {len(pages)}</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "📚 <b>محتوى الصفحة</b>\n"
        f"{html.escape(body[:3000])}\n\n"
        "━━━━━━━━━━━━━━\n"
        "🤖 <b>الشرح والاختبار: الذكاء الاصطناعي</b>"
    )[:3900]
