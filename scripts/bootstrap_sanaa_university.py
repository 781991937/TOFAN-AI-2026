"""Idempotently seed the initial Sana'a University structure.

Only verified/high-level units are seeded here. Detailed colleges, programs,
specializations, courses, and study plans are added later from approved data.

Usage:
    python scripts/bootstrap_sanaa_university.py
"""

from sqlalchemy import select

from app.db.models import AcademicUnit, Institution
from app.db.session import SessionLocal

INSTITUTION_NAME = "جامعة صنعاء"
INSTITUTION_CODE = "SU"

UNITS = (
    {
        "name": "مركز الحاسب الآلي",
        "unit_type": "center",
        "is_active": True,
        "description": "مركز أكاديمي بجامعة صنعاء. يحتوي على برامج الدبلوم والتدريب وفق البيانات المعتمدة التي تُضاف لاحقًا.",
    },
    {
        "name": "كلية الحاسوب وتكنولوجيا المعلومات",
        "unit_type": "college",
        "is_active": True,
        "description": "الاسم المختصر داخل الأكاديمية: كلية الحاسوب. تضم برامج الحوسبة وتكنولوجيا المعلومات، وتُضاف البرامج والخطط المعتمدة لاحقًا.",
    },
    {
        "name": "كليات أخرى — قيد الإنشاء",
        "unit_type": "college_placeholder",
        "is_active": False,
        "description": "حاوية مؤقتة للكليات التي ستُضاف مستقبلًا بعد نجاح المشروع وتوفير البيانات الأكاديمية المعتمدة. لا تحتوي على مواد أو مقررات فعالة.",
    },
)


def get_or_create_institution(db):
    institution = db.scalar(
        select(Institution).where(Institution.code == INSTITUTION_CODE)
    )
    if institution is None:
        institution = Institution(
            name=INSTITUTION_NAME,
            code=INSTITUTION_CODE,
            description="الجامعة الأولى في اليمن — الهيكل الأكاديمي الأساسي لمنصة أكاديمية طوفان الذكية.",
            is_active=True,
        )
        db.add(institution)
        db.flush()
    return institution


def get_or_create_unit(db, institution, data):
    unit = db.scalar(
        select(AcademicUnit).where(
            AcademicUnit.institution_id == institution.id,
            AcademicUnit.parent_id.is_(None),
            AcademicUnit.name == data["name"],
        )
    )
    if unit is None:
        unit = AcademicUnit(
            institution_id=institution.id,
            parent_id=None,
            **data,
        )
        db.add(unit)
    else:
        unit.unit_type = data["unit_type"]
        unit.is_active = data["is_active"]
        unit.description = data["description"]
    return unit


def main():
    with SessionLocal() as db:
        institution = get_or_create_institution(db)

        for data in UNITS:
            get_or_create_unit(db, institution, data)

        db.commit()

        print(f"Initialized: {institution.name} ({institution.code})")
        for unit in db.scalars(
            select(AcademicUnit)
            .where(AcademicUnit.institution_id == institution.id)
            .order_by(AcademicUnit.name)
        ):
            state = "ACTIVE" if unit.is_active else "UNDER_CONSTRUCTION"
            print(f"- {unit.name}: {state}")


if __name__ == "__main__":
    main()
