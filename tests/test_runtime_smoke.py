import importlib


def test_core_runtime_imports():
    runtime = importlib.import_module("app.core.runtime")
    automation = importlib.import_module("app.core.automation_engine")
    ai = importlib.import_module("app.core.ai_engine")
    assert hasattr(runtime, "PythonRuntime")
    assert hasattr(automation, "AutomationEngine")
    assert hasattr(ai, "AIEngine")


def test_bot_router_imports():
    modules = [
        "app.bot.sections",
        "app.bot.ai_navigation",
        "app.bot.ai_pages",
        "app.bot.ai_quizzes",
        "app.bot.ai_isolation",
        "app.bot.library",
        "app.bot.bot_library_isolation",
        "app.bot.automation",
        "app.bot.bot_page_images",
        "app.bot.automation_lesson",
        "app.bot.quiz_engine",
    ]
    for name in modules:
        module = importlib.import_module(name)
        assert hasattr(module, "router"), name


def test_no_legacy_page_imports():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    forbidden = (
        "from app.bot.sections import page_text",
        "from app.bot.sections import page_keyboard",
        "from app.bot.sections import key, pos, title",
    )
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"legacy import found in {path}: {token}"


def test_quiz_timeout_is_15_seconds():
    from app.bot.quiz_engine import QUESTION_TIMEOUT

    assert QUESTION_TIMEOUT == 15


def test_sections_are_isolated():
    from app.bot.bot_library_isolation import _is_ai_category

    assert _is_ai_category("🤖 مقدمة الذكاء الاصطناعي")
    assert not _is_ai_category("💻 البرمجة")


def test_pdf_stack_uses_supported_api():
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "TOFAN PDF PRECHECK")
    assert "TOFAN PDF PRECHECK" in page.get_text()
    document.close()
