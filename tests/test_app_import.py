def test_fastapi_application_imports():
    from app.main import app

    assert app.title == "TOFAN Smart Academy"
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/manager/dashboard" in paths
    assert "/manager/students/{user_id}/snapshot" in paths
