def test_fastapi_application_imports():
    from app.main import app

    assert app.title == "TOFAN Smart Academy"
    assert any(route.path == "/manager/dashboard" for route in app.routes)
    assert any(route.path == "/manager/students/{user_id}/snapshot" for route in app.routes)
