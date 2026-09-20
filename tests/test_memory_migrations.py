from sqlalchemy import create_engine, inspect

from app.db.migrations import run_migrations


def test_agent_conversation_memory_migration_is_idempotent():
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE agent_conversations (
                id VARCHAR(36) PRIMARY KEY,
                agent_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL
            )
            """
        )

    first = run_migrations(engine)
    second = run_migrations(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("agent_conversations")}

    assert first == [
        "agent_conversations.memory_summary",
        "agent_conversations.memory_updated_at",
    ]
    assert second == []
    assert {"memory_summary", "memory_updated_at"} <= columns
