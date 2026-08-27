from __future__ import annotations

import io

import pymupdf
from aiogram import Bot


async def download_telegram_file(bot: Bot, file_id: str) -> tuple[bytes, str]:
    if not file_id:
        raise ValueError("لا يوجد file_id للملف الأصلي.")
    telegram_file = await bot.get_file(file_id)
    if not telegram_file.file_path:
        raise ValueError("تعذر الوصول إلى الملف الأصلي في Telegram.")
    buffer = io.BytesIO()
    await bot.download_file(telegram_file.file_path, destination=buffer)
    data = buffer.getvalue()
    if not data:
        raise ValueError("الملف الأصلي فارغ.")
    return data, telegram_file.file_path


def render_pdf_bytes(pdf_bytes: bytes, page_index: int) -> bytes:
    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if page_index < 0 or page_index >= len(document):
            raise IndexError("رقم الصفحة خارج نطاق الملف.")
        page = document.load_page(page_index)
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
        return pixmap.tobytes("jpeg", jpg_quality=84)
    finally:
        document.close()


async def render_telegram_pdf_page(bot: Bot, file_id: str, page_index: int) -> bytes:
    pdf_bytes, file_path = await download_telegram_file(bot, file_id)
    if not file_path.lower().endswith(".pdf") and not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("هذا الملف ليس PDF قابلًا للرسم كصفحة أصلية.")
    return render_pdf_bytes(pdf_bytes, page_index)
