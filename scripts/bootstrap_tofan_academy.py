"""Bootstrap the native TOFAN Academy organization and starter specializations.

This is intentionally NOT a copy of any university hierarchy. University
curricula are reference data; TOFAN organizes learning by foundations, levels,
tracks, and projects.
"""

from sqlalchemy import select

from app.db.models import AcademicUnit, Institution, OrganizationType
from app.db.session import SessionLocal

TOFAN_CODE = "TOFAN"

# A specialization is active only when its TOFAN curriculum is registered
# in docs/curricula/specialty_structure_v1.json. This prevents the UI from
# advertising an active specialization that has no actual global curriculum.
SPECIALIZATIONS = (
    ("الذكاء الاصطناعي", True),
    ("علوم الحاسوب", True),
    ("تكنولوجيا المعلومات", False),
    ("الأمن السيبراني", True),
    ("نظم المعلومات", False),
    ("علم البيانات", True),
    ("هندسة البرمجيات", True),
    ("التصميم الجرافيكي والملتيميديا", False),
)


def main():
    with SessionLocal() as db:
        academy = db.scalar(select(Institution).where(Institution.code == TOFAN_CODE))
        if academy is None:
            academy = Institution(
                name="أكاديمية طوفان الذكية",
                code=TOFAN_CODE,
                organization_type=OrganizationType.ACADEMY,
                description=(
                    "منصة تعليمية مستقلة بمنهج طوفان الخاص. "
                    "لا تعتمد الهيكل الجامعي كمنهج إجباري."
                ),
                is_active=is_active,
            )
            db.add(academy)
            db.flush()
        else:
            academy.organization_type = OrganizationType.ACADEMY
            academy.is_active = True

        for name, is_active in SPECIALIZATIONS:
            item = db.scalar(
                select(AcademicUnit).where(
                    AcademicUnit.institution_id == academy.id,
                    AcademicUnit.parent_id.is_(None),
                    AcademicUnit.name == name,
                )
            )
            if item is None:
                item = AcademicUnit(
                    institution_id=academy.id,
                    name=name,
                    unit_type="specialization",
                    description=(
                        "تخصص داخل أكاديمية طوفان. "
                        "تُبنى خطته من أساسيات التخصص ثم المستويات والمسارات والمشاريع."
                    ),
                    is_active=True,
                )
                db.add(item)
            else:
                item.unit_type = "specialization"
                item.is_active = is_active

        db.commit()
        print(f"TOFAN Academy ready: {academy.id}")
        print(f"Specializations ensured: {len(SPECIALIZATIONS)} (active: {sum(1 for _, active in SPECIALIZATIONS if active)})")


if __name__ == "__main__":
    main()
