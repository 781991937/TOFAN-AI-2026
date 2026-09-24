from pathlib import Path


def test_student_shell_contains_required_modules():
    html = Path("web/index.html").read_text(encoding="utf-8")
    for module in ("app.js", "assessments.js", "student-files.js", "subscriptions.js"):
        assert module in html


def test_student_modules_use_api_calls():
    for file_name in ("web/app.js", "web/assessments.js", "web/student-files.js", "web/subscriptions.js"):
        source = Path(file_name).read_text(encoding="utf-8")
        assert "fetch(" in source or "api(" in source


def test_web_shell_exposes_passkey_login():
    html = Path("web/index.html").read_text(encoding="utf-8")
    source = Path("web/app.js").read_text(encoding="utf-8")
    assert "passkeyLoginBtn" in html
    assert "/auth/passkey/options" in source
    assert "/auth/passkey/complete" in source
    assert "navigator.credentials.get" in source


def test_mobile_shell_contains_splash_bottom_navigation_and_manager_entry():
    html = Path("web/index.html").read_text(encoding="utf-8")
    assert 'id="splashScreen"' in html
    assert 'id="mobileBottomNav"' in html
    for view in ("home", "curriculum", "assessments", "notifications", "profile"):
        assert f'data-view="{view}"' in html
    assert '/manager/dashboard-ui' in html



def test_voice_controls_are_wired_into_teacher_and_file_learning():
    app_source = Path("web/app.js").read_text(encoding="utf-8")
    file_source = Path("web/student-files.js").read_text(encoding="utf-8")
    for marker in ("SpeechRecognition", "speechSynthesis", "createVoiceControls", "voiceOutput"):
        assert marker in app_source
    assert "createVoiceControls(input,send)" in file_source
    assert "speakText" in file_source


def test_navigation_uses_collection_for_all_nav_buttons():
    source = Path("web/app.js").read_text(encoding="utf-8")
    assert '$$(".nav-btn").forEach' in source
    assert 'function showView(view){$(".nav-btn").forEach' not in source
