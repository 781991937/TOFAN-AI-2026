def test_fastapi_application_imports():
    from app.main import app
    from app.api.main_manager import router as main_manager_router
    from app.api.manager_dashboard import router as manager_dashboard_router

    assert app.title == "TOFAN Smart Academy"
    assert any(getattr(route, "path", None) == "/manager/dashboard" for route in main_manager_router.routes)
    assert any(getattr(route, "path", None) == "/manager/dashboard-ui" for route in manager_dashboard_router.routes)
    assert any(
        getattr(route, "path", None) == "/manager/students/{user_id}/snapshot"
        for route in main_manager_router.routes
    )


def test_academy_content_routes_are_registered():
    from app.main import app

    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/admin/content" in paths
    assert "/admin/content/lectures/{lecture_id}/files" in paths
    assert "/admin/content/{file_id}/status" in paths
