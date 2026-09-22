from pathlib import Path


def test_student_shell_contains_required_modules():
    html = Path("web/index.html").read_text(encoding="utf-8")
    for module in ("app.js", "assessments.js", "student-files.js", "subscriptions.js"):
        assert module in html


def test_student_modules_use_api_calls():
    for file_name in ("web/app.js", "web/assessments.js", "web/student-files.js", "web/subscriptions.js"):
        source = Path(file_name).read_text(encoding="utf-8")
        assert "fetch(" in source or "api(" in source
