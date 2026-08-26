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
        "app.bot.main",
        "app.bot.sections",
        "app.bot.ai_navigation",
        "app.bot.ai_pages",
        "app.bot.ai_quizzes",
        "app.bot.library",
        "app.bot.automation",
        "app.bot.automation_lesson",
        "app.bot.quiz_engine",
    ]
    for name in modules:
        module = importlib.import_module(name)
        assert hasattr(module, "router"), name


def test_no_legacy_page_imports():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    forbidden = ("from app.bot.sections import page_text", "from app.bot.sections import page_keyboard")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"legacy import found in {path}: {token}"


def test_quiz_timeout_is_15_seconds():
    from app.bot.quiz_engine import QUESTION_TIMEOUT

    assert QUESTION_TIMEOUT == 15
