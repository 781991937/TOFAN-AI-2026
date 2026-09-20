"""Authorization rules for agent memory."""

from sqlalchemy.orm import Session

from .memory import AgentMemoryItem, memory_deletable_by, memory_readable_by, memory_writable_by


class MemoryAuthorizationError(PermissionError):
    """Raised when an agent crosses its configured memory boundary."""


class MemoryPolicy:
    @staticmethod
    def require_read(db: Session, item: AgentMemoryItem, agent_id: str) -> None:
        if not memory_readable_by(db, item, agent_id):
            raise MemoryAuthorizationError("Agent is not allowed to read this memory.")

    @staticmethod
    def require_write(db: Session, item: AgentMemoryItem, agent_id: str) -> None:
        if not memory_writable_by(db, item, agent_id):
            raise MemoryAuthorizationError("Agent is not allowed to write this memory.")

    @staticmethod
    def require_delete(db: Session, item: AgentMemoryItem, agent_id: str) -> None:
        if not memory_deletable_by(db, item, agent_id):
            raise MemoryAuthorizationError("Agent is not allowed to delete this memory.")
