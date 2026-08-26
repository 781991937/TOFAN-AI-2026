from __future__ import annotations

import io

import fitz
from aiogram import Bot


async def render_telegram_pdf_page(bot: Bot, file_id: str, page_index: int) -> bytes:
    """Download the original Telegram PDF and render one page as a compact JPEG.

    The PDF does not need to exist on Render's local disk: Telegram is the durable
    source via file_id. This keeps page navigation working after restarts/redeploys.
    """
    if not file_id:
        raise ValueError("لا يوجد file_id للملف الأصلي.")

    telegram_file = await bot.get_file(file_id)
    if not telegram_file.file_path:
        raise ValueError("تعذر الوصول إلى الملف الأصلي في Telegram.")

    pdf_buffer = io.BytesIO()
    await bot.download_file(telegram_file.file_path, destination=pdf_buffer)
    pdf_bytes = pdf_buffer.getvalue()
    if not pdf_bytes:
        raise ValueError("الملف الأصلي فارغ.")

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if page_index < 0 or page_index >= len(document):
            raise IndexError("رقم الصفحة خارج نطاق الملف.")
        page = document.load_page(page_index)
        # A moderate scale keeps Arabic text sharp on phones without producing
        # oversized Telegram photos.
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        image = pixmap.tobytes("jpeg", jpg_quality=84)
        return image
    finally:
        document.close()
