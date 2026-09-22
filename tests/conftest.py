from pathlib import Path

def pytest_runtest_teardown(item, nextitem):
    try:
        from app.main import app
        paths = [getattr(route, "path", None) for route in app.routes]
        Path("/tmp/tofan-route-debug.log").open("a", encoding="utf-8").write(
            f"{item.nodeid}\t{len(paths)}\t{paths!r}\n"
        )
    except Exception as exc:
        Path("/tmp/tofan-route-debug.log").open("a", encoding="utf-8").write(
            f"{item.nodeid}\tERROR\t{exc!r}\n"
        )
