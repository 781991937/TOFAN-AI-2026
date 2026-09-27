"""Owner/admin content management for academy lectures."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.authorization import require_owner_or_admin
from app.auth.dependencies import get_db
from app.agents.academy_access_policy import validate_content_status
from app.agents.curriculum_content_generator import (
    CurriculumContentGenerationError,
    generate_course_preview,
    save_course_preview,
)
from app.agents.providers import AgentProviderError
from app.db.models import ContentFile, ContentStatus, Lecture, TeachingSource
from app.files.extractor import FileExtractionError, extract_teaching_text
from app.storage import get_storage

router = APIRouter(prefix="/admin/content", tags=["admin-content"])

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
MAX_FILE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt"}


class ContentStatusUpdate(BaseModel):
    status: ContentStatus


class CurriculumPreviewRequest(BaseModel):
    course_id: str = Field(min_length=1, max_length=36)
    specialty_id: str | None = Field(default=None, min_length=1, max_length=100)


class CurriculumPreviewSaveRequest(BaseModel):
    preview_token: str = Field(min_length=20, max_length=200000)


def _preview_secret() -> bytes:
    configured = os.getenv("TOFAN_PREVIEW_SECRET") or os.getenv("AUTH_OTP_PEPPER")
    if not configured:
        if os.getenv("TOFAN_ENV", "development").lower() == "production":
            raise HTTPException(
                status_code=503,
                detail="TOFAN_PREVIEW_SECRET or AUTH_OTP_PEPPER is required in production.",
            )
        configured = "tofan-development-preview-secret"
    return configured.encode("utf-8")


def _encode_preview(payload: dict) -> str:
    raw = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    signature = hmac.new(
        _preview_secret(), encoded.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return f"{encoded}.{signature}"


def _decode_preview(token: str) -> dict:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(
            _preview_secret(), encoded.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid curriculum preview token.")
    if not isinstance(payload, dict) or float(payload.get("expires_at", 0)) < time.time():
        raise HTTPException(status_code=410, detail="The curriculum preview has expired.")
    return payload


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

    storage = get_storage()
    stored = storage.put_bytes(data, suffix=suffix, prefix="academy")

    try:
        row = ContentFile(
            lecture_id=lecture_id,
            original_name=filename,
            storage_key=stored.key,
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
        storage.delete(stored.key)
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

    try:
        validate_content_status(db, content_file=row, requested_status=payload.status.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row.status = payload.status
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.post("/curriculum/generate-preview")
def generate_curriculum_preview(
    payload: CurriculumPreviewRequest,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    """Generate and validate content without saving it."""
    try:
        result = generate_course_preview(
            db,
            course_id=payload.course_id,
            specialty_id=payload.specialty_id,
        )
    except CurriculumContentGenerationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AgentProviderError as exc:
        raise HTTPException(
            status_code=502,
            detail="The configured AI provider could not generate content.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Curriculum preview generation failed."
        ) from exc

    expires_at = int(time.time()) + 15 * 60
    preview_token = _encode_preview({**result, "expires_at": expires_at})
    return {
        "status": "preview",
        "expires_at": expires_at,
        "preview_token": preview_token,
        **result,
    }


@router.post("/curriculum/save-preview")
def save_curriculum_preview(
    payload: CurriculumPreviewSaveRequest,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    """Revalidate and persist content from an unexpired preview."""
    preview = _decode_preview(payload.preview_token)
    try:
        result = save_course_preview(
            db,
            specialty_id=str(preview["specialty_id"]),
            course_id=str(preview["course_id"]),
            preview=preview["preview"],
        )
    except (KeyError, TypeError, CurriculumContentGenerationError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "saved", **result}
