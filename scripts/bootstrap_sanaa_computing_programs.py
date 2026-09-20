"""Seed verified Sana'a University computing programs.

Sources:
- Sana'a University Computer Center public program pages.
- Sana'a University Faculty of Computer and Information Technology
  coordination announcement.
- Sana'a University announcement approving the new two-year AI and IT
  diploma programs at the Computer Center.

This script creates only high-level program units. Course/semester plans
must be imported from approved curriculum documents later.
"""

from sqlalchemy import select

from app.db.models import AcademicUnit, Institution
from app.db.session import SessionLocal

INSTITUTION_CODE = "SU"

PROGRAMS = {
    "مركز الحاسب الآلي": (
        ("دبلوم نظم المعلومات", "program"),
        ("دبلوم الجرافيكس والوسائط المتعددة", "program"),
        ("دبلوم الشبكات وأمن المعلومات", "program"),
        ("دبلوم تطبيقات الموبايل والإنترنت", "program"),
        ("دبلوم الذكاء الاصطناعي", "program"),
        ("دبلوم تكنولوجيا المعلومات", "program"),
    ),
    "كلية الحاسوب وتكنولوجيا المعلومات": (
        ("علوم الحاسوب", "specialization"),
        ("تكنولوجيا المعلومات", "specialization"),
        ("الأمن السيبراني", "specialization"),
        ("نظم المعلومات", "specialization"),
        ("الذكاء الاصطناعي", "specialization"),
        ("علم البيانات", "specialization"),
    ),
}


def find_root_unit(db, institution_id, name):
    return db.scalar(
        select(AcademicUnit).where(
            AcademicUnit.institution_id == institution_id,
            AcademicUnit.parent_id.is_(None),
            AcademicUnit.name == name,
        )
    )


def get_or_create_program(db, institution_id, parent, name, unit_type):
    item = db.scalar(
        select(AcademicUnit).where(
            AcademicUnit.institution_id == institution_id,
            AcademicUnit.parent_id == parent.id,
            AcademicUnit.name == name,
        )
    )
    if item is None:
        item = AcademicUnit(
            institution_id=institution_id,
            parent_id=parent.id,
            name=name,
            unit_type=unit_type,
            description=(
                "برنامج/تخصص موثق من المصادر المنشورة لجامعة صنعاء. "
                "تُضاف الخطة الدراسية والمقررات بعد اعتمادها وإدخالها إلى المنصة."
            ),
            is_active=True,
        )
        db.add(item)
    else:
        item.unit_type = unit_type
        item.is_active = True
    return item


def main():
    with SessionLocal() as db:
        institution = db.scalar(
            select(Institution).where(Institution.code == INSTITUTION_CODE)
        )
        if institution is None:
            raise RuntimeError(
                "جامعة صنعاء غير موجودة. شغّل bootstrap_sanaa_university.py أولاً."
            )

        created = []
        for parent_name, programs in PROGRAMS.items():
            parent = find_root_unit(db, institution.id, parent_name)
            if parent is None:
                raise RuntimeError(f"الوحدة الأكاديمية غير موجودة: {parent_name}")

            for name, unit_type in programs:
                item = get_or_create_program(
                    db, institution.id, parent, name, unit_type
                )
                created.append((parent.name, item.name, item.unit_type))

        db.commit()

        for parent, name, unit_type in created:
            print(f"- {parent} / {name} [{unit_type}]")
        print(f"Total verified program/specialization units: {len(created)}")


if __name__ == "__main__":
    main()
