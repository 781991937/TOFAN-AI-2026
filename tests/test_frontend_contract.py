from pathlib import Path
import re


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
    for selector in (".nav-btn", ".tab", ".course-button", ".lesson-button", ".notification-read"):
        assert '$("' + selector + '").forEach' in source
        assert re.search(r'(?<!\\$)\\$(?:\\(\\"' + re.escape(selector) + r'\\"\\))\\.forEach', source) is None
    assert 'document.addEventListener("click",event=>' in source
    assert "async function showView(view){" in source


def test_owner_dashboard_does_not_depend_on_student_onboarding():
    source = Path("web/app.js").read_text(encoding="utf-8")
    start = source.index("async function loadDashboard()")
    end = source.index("async function renderSpecialties", start)
    dashboard = source[start:end]
    assert 'api("/users/me/roles")' in dashboard
    assert 'if(isOwner)' in dashboard
    assert 'await loadOnboardingState()' in dashboard
    assert dashboard.index('if(isOwner)') < dashboard.index('await loadOnboardingState()')
