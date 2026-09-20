from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import ContentFile, ContentStatus, Institution, TeachingSource, User


def test_academy_content_uses_global_curriculum_source():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)

    user = User(display_name="Owner", email="owner@example.com")
    institution = Institution(
        name="TOFAN Smart Academy",
        code="TOFAN-ACADEMY",
        organization_type="academy",
    )
    db.add_all([user, institution])
    db.flush()

    content = ContentFile(
        original_name="lesson.pdf",
        storage_key="academy/lesson.pdf",
        teaching_source=TeachingSource.GLOBAL_CURRICULUM,
        status=ContentStatus.DRAFT,
        extracted_text="Academy lesson content.",
    )
    db.add(content)
    db.flush()

    assert content.teaching_source == TeachingSource.GLOBAL_CURRICULUM
    assert content.status == ContentStatus.DRAFT
