"""Small idempotent schema migrations for TOFAN Academy.

This module intentionally avoids a heavyweight migration dependency while the
project is still establishing its database foundation. Each migration checks
the live schema before changing it and works with SQLite and PostgreSQL.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _quote_identifier(engine: Engine, identifier: str) -> str:
    return engine.dialect.identifier_preparer.quote(identifier)


def add_column_if_missing(
    engine: Engine,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> bool:
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
    """Add persistent-memory columns to existing agent_conversations tables."""
    changes: list[str] = []

    if add_column_if_missing(
        engine,
        "agent_conversations",
        "memory_summary",
        "TEXT",
    ):
        changes.append("agent_conversations.memory_summary")

    if add_column_if_missing(
        engine,
        "agent_conversations",
        "memory_updated_at",
        "DATETIME",
    ):
        changes.append("agent_conversations.memory_updated_at")

    return changes


def run_migrations(engine: Engine) -> list[str]:
    """Run all current idempotent migrations and return changed columns."""
    return migrate_agent_conversation_memory(engine)

