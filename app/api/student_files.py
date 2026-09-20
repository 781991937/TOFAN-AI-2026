"""Student-file upload and teaching-library endpoints."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.models import Agent, AgentKind, AgentStatus
from app.agents.teaching_policy import TeachingAccessError, register_student_file, get_or_create_usage
from app.auth.dependencies import get_current_user, get_db
from app.db.models import ContentFile, ContentStatus, TeachingSource, User
from app.files.extractor import FileExtractionError, extract_teaching_text

router = APIRouter(prefix="/student/files", tags=["student-files"])

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
MAX_FILE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def _teacher(db: Session, slug: str) -> Agent:
    agent = db.scalar(
        select(Agent).where(
            Agent.slug == slug,
            Agent.kind == AgentKind.TEACHER,
            Agent.status == AgentStatus.ACTIVE,
        )
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Active teacher agent not found.")
    return agent


@router.post("/upload", status_code=201)
async def upload_student_file(
    teacher_slug: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    teacher = _teacher(db, teacher_slug)
    filename = (file.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(status_code=415, detail="Only PDF, DOCX, and TXT files are supported.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_FILE_SIZE_MB} MB limit.")

    try:
        extracted_text, page_count = extract_teaching_text(filename, data)
    except FileExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not extracted_text.strip():
        raise HTTPException(status_code=422, detail="No readable teaching text was found in the file.")

    usage = get_or_create_usage(
        db,
        user_id=actor.id,
        agent_id=teacher.id,
        source=TeachingSource.STUDENT_FILES,
    )
    if usage.files_used >= usage.files_limit:
        raise HTTPException(
            status_code=429,
            detail="The free student-file limit of 3 files for this 24-hour window has been reached.",
        )

    storage_root = Path(os.getenv("TOFAN_UPLOAD_DIR", "data/uploads"))
    user_dir = storage_root / actor.id
    user_dir.mkdir(parents=True, exist_ok=True)
    storage_name = f"{uuid4().hex}{suffix}"
    storage_path = user_dir / storage_name
    storage_path.write_bytes(data)

    content_file = ContentFile(
        original_name=filename,
        storage_key=str(storage_path),
        mime_type=file.content_type,
        status=ContentStatus.PRIVATE,
        extracted_text=extracted_text,
        size_bytes=len(data),
        page_count=page_count,
        uploaded_by_user_id=actor.id,
        teaching_source=TeachingSource.STUDENT_FILES,
    )
    db.add(content_file)
    db.flush()

    try:
        register_student_file(
            db,
            user_id=actor.id,
            agent_id=teacher.id,
            content_file=content_file,
        )
        db.commit()
        db.refresh(content_file)
    except TeachingAccessError as exc:
        db.rollback()
        storage_path.unlink(missing_ok=True)
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        storage_path.unlink(missing_ok=True)
        raise

    return {
        "file_id": content_file.id,
        "teacher_agent_id": teacher.id,
        "teacher_slug": teacher.slug,
        "original_name": content_file.original_name,
        "mime_type": content_file.mime_type,
        "size_bytes": content_file.size_bytes,
        "page_count": content_file.page_count,
        "text_characters": len(extracted_text),
        "teaching_source": TeachingSource.STUDENT_FILES,
        "files_used": usage.files_used,
        "files_remaining": max(0, usage.files_limit - usage.files_used),
        "next_step": "start_teaching",
    }


@router.get("")
def list_student_files(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    rows = db.scalars(
        select(ContentFile)
        .where(
            ContentFile.uploaded_by_user_id == actor.id,
            ContentFile.teaching_source == TeachingSource.STUDENT_FILES,
        )
        .order_by(ContentFile.uploaded_at.desc())
    ).all()
    return {
        "files": [
            {
                "file_id": row.id,
                "original_name": row.original_name,
                "mime_type": row.mime_type,
                "size_bytes": row.size_bytes,
                "page_count": row.page_count,
                "text_characters": len(row.extracted_text or ""),
                "uploaded_at": row.uploaded_at,
            }
            for row in rows
        ]
    }


@router.get("/{file_id}")
def get_student_file(
    file_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    row = db.get(ContentFile, file_id)
    if row is None or row.uploaded_by_user_id != actor.id or row.teaching_source != TeachingSource.STUDENT_FILES:
        raise HTTPException(status_code=404, detail="Student file not found.")
    return {
        "file_id": row.id,
        "original_name": row.original_name,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "page_count": row.page_count,
        "text": row.extracted_text,
        "uploaded_at": row.uploaded_at,
    }
