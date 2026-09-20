"""Owner/admin content management for academy lectures."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_db
from app.db.models import ContentFile, ContentStatus, Lecture, TeachingSource
from app.files.extractor import FileExtractionError, extract_teaching_text

router = APIRouter(prefix="/admin/content", tags=["admin-content"])

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
MAX_FILE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt"}


class ContentStatusUpdate(BaseModel):
    status: ContentStatus


def _serialize(row: ContentFile) -> dict:
    return {
        "file_id": row.id,
        "lecture_id": row.lecture_id,
        "original_name": row.original_name,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "page_count": row.page_count,
        "status": row.status,
        "text_characters": len(row.extracted_text or ""),
        "uploaded_at": row.uploaded_at,
    }


@router.get("")
def list_content(
    lecture_id: str | None = None,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    query = select(ContentFile).where(ContentFile.lecture_id.is_not(None))
    if lecture_id:
        query = query.where(ContentFile.lecture_id == lecture_id)
    rows = db.scalars(query.order_by(ContentFile.uploaded_at.desc())).all()
    return {"files": [_serialize(row) for row in rows]}


@router.post("/lectures/{lecture_id}/files", status_code=201)
async def upload_lecture_file(
    lecture_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    lecture = db.get(Lecture, lecture_id)
    if lecture is None:
        raise HTTPException(status_code=404, detail="Lecture not found.")

    filename = (file.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail="Only PDF, DOCX, and TXT files are supported.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_FILE_SIZE_MB} MB limit.",
        )

    try:
        extracted_text, page_count = extract_teaching_text(filename, data)
    except FileExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not extracted_text.strip():
        raise HTTPException(
            status_code=422,
            detail="No readable teaching text was found in the file.",
        )

    storage_root = Path(os.getenv("TOFAN_UPLOAD_DIR", "data/uploads"))
    content_dir = storage_root / "academy"
    content_dir.mkdir(parents=True, exist_ok=True)
    storage_name = f"{uuid4().hex}{suffix}"
    storage_path = content_dir / storage_name

    try:
        storage_path.write_bytes(data)
        row = ContentFile(
            lecture_id=lecture_id,
            original_name=filename,
            storage_key=str(storage_path),
            mime_type=file.content_type,
            status=ContentStatus.DRAFT,
            teaching_source=TeachingSource.GLOBAL_CURRICULUM,
            extracted_text=extracted_text,
            size_bytes=len(data),
            page_count=page_count,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        storage_path.unlink(missing_ok=True)
        raise

    return _serialize(row)


@router.patch("/{file_id}/status")
def update_content_status(
    file_id: str,
    payload: ContentStatusUpdate,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    row = db.get(ContentFile, file_id)
    if row is None or row.lecture_id is None:
        raise HTTPException(status_code=404, detail="Academy content file not found.")

    row.status = payload.status
    db.commit()
    db.refresh(row)
    return _serialize(row)
