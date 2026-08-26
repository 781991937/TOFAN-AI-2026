from datetime import datetime

from zoneinfo import ZoneInfo

_YEMEN = ZoneInfo("Asia/Aden")


def bot_brand() -> str:
    return (
        "<pre>"
        "╔══════════════════════════════╗\n"
        "║      🤖  TOFAN AI 2026      ║\n"
        "║                              ║\n"
        "║        ╭─────────╮           ║\n"
        "║        │  ◉   ◉  │           ║\n"
        "║        │    ▱    │  🧠       ║\n"
        "║        ╰───┬─────╯           ║\n"
        "║            ╰── AI             ║\n"
        "╚══════════════════════════════╝"
        "</pre>"
    )


def brand_header() -> str:
    return bot_brand() + "\n\n🌟 <b>مساعدك الجامعي الذكي</b>"


def digital_clock() -> str:
    now = datetime.now(_YEMEN)
    hour = now.hour % 12 or 12
    period = "ص" if now.hour < 12 else "م"
    return f"🕐 <b>{hour:02d}:{now.minute:02d}:{now.second:02d} {period}</b>  •  📅 <b>{now.day:02d}/{now.month:02d}/{now.year}</b>"
