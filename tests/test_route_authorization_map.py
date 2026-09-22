from fastapi.routing import APIRoute

from app.main import app


def test_sensitive_routes_have_dependencies():
    sensitive = (
        "/admin/agents",
        "/admin/notifications/broadcast",
        "/manager/payments",
        "/manager/assessments",
        "/manager/audit-log",
    )
    routes = {route.path: route for route in app.routes if isinstance(route, APIRoute)}
    for path in sensitive:
        assert path in routes
        assert routes[path].dependant.dependencies, path
