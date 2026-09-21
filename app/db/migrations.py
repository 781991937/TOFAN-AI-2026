"""Small idempotent schema migrations for TOFAN Academy."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _quote_identifier(engine: Engine, identifier: str) -> str:
    return engine.dialect.identifier_preparer.quote(identifier)


def add_column_if_missing(engine: Engine, table_name: str, column_name: str, column_sql: str) -> bool:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return False
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in existing:
        return False
    table = _quote_identifier(engine, table_name)
    column = _quote_identifier(engine, column_name)
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_sql}"))
    return True


def migrate_agent_conversation_memory(engine: Engine) -> list[str]:
    changes: list[str] = []
    if add_column_if_missing(engine, "agent_conversations", "memory_summary", "TEXT"):
        changes.append("agent_conversations.memory_summary")
    if add_column_if_missing(engine, "agent_conversations", "memory_updated_at", "DATETIME"):
        changes.append("agent_conversations.memory_updated_at")
    return changes


def migrate_agent_memory_scopes(engine: Engine) -> list[str]:
    changes: list[str] = []
    for name, sql in (("owner_agent_id", "VARCHAR(36)"), ("memory_scope", "VARCHAR(30)")):
        if add_column_if_missing(engine, "agent_memory_items", name, sql):
            changes.append(f"agent_memory_items.{name}")
    inspector = inspect(engine)
    if "agent_memory_items" in inspector.get_table_names():
        with engine.begin() as connection:
            result = connection.execute(text(
                "UPDATE agent_memory_items SET owner_agent_id = "
                "(SELECT agent_id FROM agent_conversations WHERE agent_conversations.id = agent_memory_items.conversation_id) "
                "WHERE owner_agent_id IS NULL"
            ))
            if result.rowcount:
                changes.append("agent_memory_items.owner_agent_id backfill")
            result = connection.execute(text(
                "UPDATE agent_memory_items SET memory_scope = 'conversation' WHERE memory_scope IS NULL"
            ))
            if result.rowcount:
                changes.append("agent_memory_items.memory_scope backfill")
    return changes


def migrate_agent_workforce_roles(engine: Engine) -> list[str]:
    changes: list[str] = []
    if add_column_if_missing(engine, "agents", "role", "VARCHAR(50) DEFAULT 'operations'"):
        changes.append("agents.role")
    return changes


def migrate_teacher_agent_course(engine: Engine) -> list[str]:
    changes: list[str] = []
    for name, sql in (
        ("teacher_course_id", "VARCHAR(36)"),
        ("teacher_institution_id", "VARCHAR(36)"),
        ("curriculum_course_id", "VARCHAR(36)"),
    ):
        if add_column_if_missing(engine, "agents", name, sql):
            changes.append(f"agents.{name}")
    return changes


def migrate_academic_structure(engine: Engine) -> list[str]:
    changes: list[str] = []
    if add_column_if_missing(engine, "academic_periods", "parent_id", "VARCHAR(36)"):
        changes.append("academic_periods.parent_id")
    for name, sql in (("year_number", "INTEGER"), ("term_number", "INTEGER")):
        if add_column_if_missing(engine, "academic_periods", name, sql):
            changes.append(f"academic_periods.{name}")
    for name, sql in (
        ("course_type", "VARCHAR(30) DEFAULT 'required'"),
        ("learning_stage", "VARCHAR(30) DEFAULT 'foundation'"),
        ("credit_hours", "INTEGER"),
        ("theory_hours", "INTEGER"),
        ("practical_hours", "INTEGER"),
        ("prerequisites", "TEXT"),
    ):
        if add_column_if_missing(engine, "courses", name, sql):
            changes.append(f"courses.{name}")
    if add_column_if_missing(engine, "institutions", "organization_type", "VARCHAR(30) DEFAULT 'university'"):
        changes.append("institutions.organization_type")
    return changes


def migrate_teaching_limits(engine: Engine) -> list[str]:
    changes: list[str] = []
    for table, columns in {
        "content_files": (
            ("uploaded_by_user_id", "VARCHAR(36)"),
            ("teaching_source", "VARCHAR(40) DEFAULT 'global_curriculum'"),
        ),
        "teaching_usage": (
            ("files_used", "INTEGER DEFAULT 0"),
            ("files_limit", "INTEGER DEFAULT 3"),
            ("free_steps_used", "INTEGER DEFAULT 0"),
            ("free_steps_limit", "INTEGER DEFAULT 5"),
            ("response_chars_used", "INTEGER DEFAULT 0"),
            ("response_chars_limit", "INTEGER DEFAULT 2000"),
            ("quota_started_at", "DATETIME"),
            ("paid_access", "BOOLEAN DEFAULT 0"),
            ("updated_at", "DATETIME"),
        ),
        "teaching_steps": (
            ("attempts", "INTEGER DEFAULT 0"),
            ("understanding_verified", "BOOLEAN DEFAULT 0"),
            ("student_confirmed", "BOOLEAN DEFAULT 0"),
            ("completed_at", "DATETIME"),
        ),
    }.items():
        for name, sql in columns:
            if add_column_if_missing(engine, table, name, sql):
                changes.append(f"{table}.{name}")
    return changes


def migrate_specialty_localization(engine: Engine) -> list[str]:
    changes: list[str] = []
    for name, sql in (("name_ar", "VARCHAR(255)"), ("name_en", "VARCHAR(255)"), ("description_ar", "TEXT"), ("description_en", "TEXT")):
        if add_column_if_missing(engine, "specialties", name, sql):
            changes.append(f"specialties.{name}")
    return changes


def migrate_specialty_themes(engine: Engine) -> list[str]:
    changes: list[str] = []
    for name, sql in (("icon", "VARCHAR(100)"), ("theme_config_json", "TEXT")):
        if add_column_if_missing(engine, "specialties", name, sql):
            changes.append(f"specialties.{name}")
    return changes


def migrate_curriculum_lesson_content(engine: Engine) -> list[str]:
    changes: list[str] = []
    for name, sql in (
        ("content_markdown", "TEXT"),
        ("source_refs_json", "TEXT"),
        ("learning_objectives_json", "TEXT"),
    ):
        if add_column_if_missing(engine, "curriculum_lessons", name, sql):
            changes.append(f"curriculum_lessons.{name}")
    return changes


def migrate_certificates(engine: Engine) -> list[str]:
    from app.db.certificate_models import Certificate
    from app.db.base import Base
    Base.metadata.create_all(bind=engine, tables=[Certificate.__table__])
    return []


def migrate_learning_progress(engine: Engine) -> list[str]:
    from app.db.progress_models import LearningProgress, LearningWeakPoint, LearningNextStep
    from app.db.base import Base
    Base.metadata.create_all(bind=engine, tables=[
        LearningProgress.__table__, LearningWeakPoint.__table__, LearningNextStep.__table__,
    ])
    return []


def migrate_notifications(engine: Engine) -> list[str]:
    from app.db.models import Notification
    from app.db.base import Base
    Base.metadata.create_all(bind=engine, tables=[Notification.__table__])
    return []


def migrate_curriculum_assessments(engine: Engine) -> list[str]:
    from app.db.assessment_models import CurriculumAssessmentAttempt, AssessmentResultReport
    from app.db.assessment_question_models import CurriculumAssessmentQuestion
    from app.db.base import Base
    Base.metadata.create_all(bind=engine, tables=[
        CurriculumAssessmentAttempt.__table__,
        AssessmentResultReport.__table__,
        CurriculumAssessmentQuestion.__table__,
    ])
    return []


def migrate_content_files(engine: Engine) -> list[str]:
    changes: list[str] = []
    for name, sql in (
        ("teaching_agent_id", "VARCHAR(36)"),
        ("extracted_text", "TEXT"),
        ("size_bytes", "INTEGER"),
        ("page_count", "INTEGER"),
        ("assessment_json", "TEXT"),
        ("assessment_generated_at", "DATETIME"),
    ):
        if add_column_if_missing(engine, "content_files", name, sql):
            changes.append(f"content_files.{name}")
    return changes


def migrate_payment_accounts(engine: Engine) -> list[str]:
    changes: list[str] = []
    if add_column_if_missing(engine, "payment_account_settings", "amount", "FLOAT"):
        changes.append("payment_account_settings.amount")
    return changes


def migrate_payment_proofs(engine: Engine) -> list[str]:
    changes: list[str] = []
    if add_column_if_missing(engine, "payment_transactions", "proof_file_id", "VARCHAR(36)"):
        changes.append("payment_transactions.proof_file_id")
    return changes


def migrate_payment_rejections(engine: Engine) -> list[str]:
    changes: list[str] = []
    if add_column_if_missing(engine, "payment_transactions", "rejection_reason", "VARCHAR(500)"):
        changes.append("payment_transactions.rejection_reason")
    return changes

def run_migrations(engine: Engine) -> list[str]:
    changes = migrate_payment_proofs(engine)
    changes.extend(migrate_payment_rejections(engine))
    changes.extend(migrate_payment_accounts(engine)
    changes.extend(migrate_agent_conversation_memory(engine)
    changes.extend(migrate_agent_memory_scopes(engine))
    changes.extend(migrate_agent_workforce_roles(engine))
    changes.extend(migrate_teacher_agent_course(engine))
    changes.extend(migrate_academic_structure(engine))
    changes.extend(migrate_teaching_limits(engine))
    changes.extend(migrate_content_files(engine))
    changes.extend(migrate_specialty_localization(engine))
    changes.extend(migrate_specialty_themes(engine))
    changes.extend(migrate_curriculum_lesson_content(engine))
    changes.extend(migrate_curriculum_assessments(engine))
    changes.extend(migrate_learning_progress(engine))
    changes.extend(migrate_certificates(engine))
    changes.extend(migrate_notifications(engine))
    return changes
