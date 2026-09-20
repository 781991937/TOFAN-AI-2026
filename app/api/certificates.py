"""Certificate endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.db.models import User
from app.certificates.service import issue_course_certificate, list_certificates

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get("")
def certificates(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return {"certificates": [
        {"id": c.id, "certificate_number": c.certificate_number, "course_id": c.course_id,
         "title": c.title, "status": c.status, "issued_at": c.issued_at.isoformat()}
        for c in list_certificates(db, actor.id)
    ]}


@router.post("/courses/{course_id}/issue")
def issue_certificate(course_id: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    certificate = issue_course_certificate(db, actor.id, course_id)
    if certificate is None:
        raise HTTPException(status_code=409, detail="Course completion is not yet verified.")
    db.commit()
    return {
        "certificate_id": certificate.id, "certificate_number": certificate.certificate_number,
        "course_id": certificate.course_id, "title": certificate.title,
        "status": certificate.status, "issued_at": certificate.issued_at.isoformat(),
    }
