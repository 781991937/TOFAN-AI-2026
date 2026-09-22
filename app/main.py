"""FastAPI application entry point for TOFAN Smart Academy."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.admin import router as admin_router
from app.api.admin_users import router as admin_users_router
from app.api.academy_admin import router as academy_admin_router
from app.api.content_admin import router as content_admin_router
from app.api.agent_admin import router as agent_admin_router
from app.api.agent_chat import router as agent_chat_router
from app.api.agent_memory import router as agent_memory_router
from app.api.agent_runtime import router as agent_runtime_router
from app.api.teacher_admin import router as teacher_admin_router
from app.api.teacher_chat import router as teacher_chat_router
from app.api.teacher_teaching import router as teacher_teaching_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.student_identity import router as student_identity_router
from app.api.student_onboarding import router as student_onboarding_router
from app.api.student_files import router as student_files_router
from app.api.academic_catalog import router as academic_catalog_router
from app.api.curriculum import router as curriculum_router
from app.api.specialty_experience import router as specialty_experience_router
from app.api.main_manager import router as main_manager_router
from app.api.notifications import router as notifications_router
from app.api.learning_progress import router as learning_progress_router
from app.api.certificates import router as certificates_router
from app.api.student_assessments import router as student_assessments_router
from app.api.manager_dashboard import router as manager_dashboard_router
from app.db.init_db import init_db
from app.db.session import SessionLocal


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="TOFAN Smart Academy", version="0.1.0", lifespan=lifespan)
app.mount("/web", StaticFiles(directory="web", html=True), name="web")


@app.get("/", include_in_schema=False)
def academy_home():
    return RedirectResponse(url="/web/")


@app.get("/health", tags=["system"])
def health():
    """Platform health endpoint used by deployment and uptime checks."""
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "TOFAN Smart Academy"}


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(student_identity_router)
app.include_router(student_onboarding_router)
app.include_router(student_files_router)
app.include_router(academic_catalog_router)
app.include_router(admin_router)
app.include_router(academy_admin_router)
app.include_router(content_admin_router)
app.include_router(admin_users_router)
app.include_router(agent_admin_router)
app.include_router(agent_chat_router)
app.include_router(agent_memory_router)
app.include_router(agent_runtime_router)
app.include_router(teacher_admin_router)
app.include_router(teacher_chat_router)
app.include_router(teacher_teaching_router)
app.include_router(main_manager_router)
app.include_router(notifications_router)
app.include_router(learning_progress_router)
app.include_router(certificates_router)
app.include_router(student_assessments_router)
app.include_router(manager_dashboard_router)
app.include_router(curriculum_router)
app.include_router(specialty_experience_router)


def main() -> None:
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
