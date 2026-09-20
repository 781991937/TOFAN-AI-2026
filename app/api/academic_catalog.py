"""Public academic catalog used by onboarding.

The catalog is reference/alignment data. It does not define the TOFAN-native
global curriculum.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db
from app.db.models import AcademicUnit, Institution

router = APIRouter(prefix="/catalog", tags=["academic-catalog"])


@router.get("/institutions")
def list_institutions(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Institution)
        .where(Institution.is_active.is_(True))
        .order_by(Institution.name)
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "name": row.name,
                "code": row.code,
                "organization_type": row.organization_type,
            }
            for row in rows
        ]
    }


@router.get("/institutions/{institution_id}/colleges")
def list_colleges(institution_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(AcademicUnit)
        .where(
            AcademicUnit.institution_id == institution_id,
            AcademicUnit.unit_type == "college",
            AcademicUnit.is_active.is_(True),
        )
        .order_by(AcademicUnit.name)
    ).all()
    return {"items": [{"id": row.id, "name": row.name} for row in rows]}


@router.get("/institutions/{institution_id}/majors")
def list_majors(institution_id: str, college_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(AcademicUnit)
        .where(
            AcademicUnit.institution_id == institution_id,
            AcademicUnit.parent_id == college_id,
            AcademicUnit.unit_type == "major",
            AcademicUnit.is_active.is_(True),
        )
        .order_by(AcademicUnit.name)
    ).all()
    return {"items": [{"id": row.id, "name": row.name} for row in rows]}
