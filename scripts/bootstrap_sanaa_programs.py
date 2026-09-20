"""Seed verified Sana'a University programs under the initial academic units.

The data is intentionally limited to program-level structure. Detailed courses,
semesters, study plans, and lecture content are added from approved source files.

Sources:
- Sana'a University FCIT official programs page.
- Sana'a University Computer Center official page.
- Sana'a University council announcement dated 2025-07-16 for the two newly
  approved two-year diploma programs.
"""

from sqlalchemy import select

from app.db.models import AcademicUnit, Institution
from app.db.session import SessionLocal

UNIVERSITY_CODE = "SU"

PROGRAMS = {
    "مركز الحاسب الآلي": [
        (
            "دبلوم الجرافيكس والوسائط المتعددة",
            "program",
            "دبلوم سنتان بعد الثانوية العامة بحسب صفحة مركز الحاسب الآلي الرسمية.",
        ),
        (
            "دبلوم نظم المعلومات",
            "program",
            "دبلوم سنتان بعد الثانوية العامة بحسب صفحة مركز الحاسب الآلي الرسمية.",
        ),
        (
            "دبلوم الشبكات وأمن المعلومات",
            "program",
            "دبلوم سنتان بعد الثانوية العامة بحسب صفحة مركز الحاسب الآلي الرسمية.",
        ),
        (
            "دبلوم تطبيقات الموبايل والإنترنت",
            "program",
            "دبلوم سنتان بعد الثانوية العامة بحسب صفحة مركز الحاسب الآلي الرسمية.",
        ),
        (
            "دبلوم تكنولوجيا المعلومات",
            "program",
            "برنامج دبلوم نظام سنتين بعد الثانوية، اعتمده مجلس جامعة صنعاء في 2025-07-16.",
        ),
        (
            "دبلوم الذكاء الاصطناعي",
            "program",
            "برنامج دبلوم نظام سنتين بعد الثانوية، اعتمده مجلس جامعة صنعاء في 2025-07-16.",
        ),
    ],
    "كلية الحاسوب وتكنولوجيا المعلومات": [
        ("بكالوريوس تكنولوجيا المعلومات", "program", "برنامج بكالوريوس."),
        ("بكالوريوس علوم الحاسوب", "program", "برنامج بكالوريوس."),
        ("بكالوريوس الذكاء الاصطناعي", "program", "برنامج بكالوريوس."),
        ("بكالوريوس نظم المعلومات", "program", "برنامج بكالوريوس."),
        ("بكالوريوس علم البيانات", "program", "برنامج بكالوريوس."),
        ("بكالوريوس الأمن السيبراني", "program", "برنامج بكالوريوس."),
        ("بكالوريوس التصميم الجرافيكي والملتيميديا", "program", "برنامج بكالوريوس."),
        ("ماجستير تكنولوجيا المعلومات", "program", "برنامج دراسات عليا — ماجستير."),
        ("ماجستير علوم الحاسوب", "program", "برنامج دراسات عليا — ماجستير."),
        ("ماجستير نظم المعلومات", "program", "برنامج دراسات عليا — ماجستير."),
        ("ماجستير الأمن السيبراني", "program", "برنامج دراسات عليا — ماجستير."),
        ("دكتوراه تكنولوجيا المعلومات", "program", "برنامج دراسات عليا — دكتوراه."),
        ("دكتوراه علوم الحاسوب", "program", "برنامج دراسات عليا — دكتوراه."),
        ("دكتوراه نظم المعلومات", "program", "برنامج دراسات عليا — دكتوراه."),
    ],
}


def main():
    with SessionLocal() as db:
        institution = db.scalar(
            select(Institution).where(Institution.code == UNIVERSITY_CODE)
        )
        if institution is None:
            raise RuntimeError(
                "جامعة صنعاء غير موجودة. شغّل bootstrap_sanaa_university.py أولاً."
            )

        created = 0
        for parent_name, programs in PROGRAMS.items():
            parent = db.scalar(
                select(AcademicUnit).where(
                    AcademicUnit.institution_id == institution.id,
                    AcademicUnit.parent_id.is_(None),
                    AcademicUnit.name == parent_name,
                )
            )
            if parent is None:
                raise RuntimeError(f"الوحدة الأكاديمية غير موجودة: {parent_name}")

            for name, unit_type, description in programs:
                existing = db.scalar(
                    select(AcademicUnit).where(
                        AcademicUnit.institution_id == institution.id,
                        AcademicUnit.parent_id == parent.id,
                        AcademicUnit.name == name,
                    )
                )
                if existing is None:
                    db.add(
                        AcademicUnit(
                            institution_id=institution.id,
                            parent_id=parent.id,
                            name=name,
                            unit_type=unit_type,
                            description=description,
                            is_active=True,
                        )
                    )
                    created += 1

        db.commit()
        print(f"Created {created} program units for {institution.name}.")


if __name__ == "__main__":
    main()
