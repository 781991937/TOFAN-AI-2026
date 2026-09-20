"""AI-assisted conversation memory compaction for the TOFAN Main Agent."""

from sqlalchemy.orm import Session

from .memory import (
    AgentConversation,
    AgentMessageRecord,
    update_memory_summary,
)
from .providers import AIProvider, AgentMessage, AgentProviderError


MEMORY_RECENT_LIMIT = 12
MEMORY_COMPACTION_THRESHOLD = 20

MEMORY_SUMMARY_SYSTEM_PROMPT = """You are the TOFAN Academy conversation-memory curator.

Create a compact, factual memory summary from the supplied conversation.
Keep only information that can improve future assistance, such as:
- stable user preferences explicitly stated by the user
- ongoing projects, goals, constraints, and decisions
- important unresolved tasks or next steps
- durable context explicitly established in the conversation

Do not invent facts, infer sensitive traits, or preserve unnecessary transient
chatter. If the existing summary conflicts with newer messages, prefer the
newer explicit message. Do not provide advice or answer the conversation.
Return only the updated summary in concise plain text.
"""


class ConversationMemoryService:
    """Maintains compact persistent memory without making chat depend on it."""

    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def should_compact(self, messages: list[AgentMessageRecord]) -> bool:
        return len(messages) > MEMORY_COMPACTION_THRESHOLD

    def compact(
        self,
        db: Session,
        conversation: AgentConversation,
        messages: list[AgentMessageRecord],
    ) -> bool:
        if not self.should_compact(messages):
            return False

        older = messages[:-MEMORY_RECENT_LIMIT]
        if not older:
            return False

        source_parts = []
        if conversation.memory_summary:
            source_parts.append("Existing memory summary:\n" + conversation.memory_summary)
        source_parts.append(
            "Older conversation to incorporate:\n"
            + "\n".join(f"{m.role}: {m.content}" for m in older)
        )

        try:
            response = self.provider.generate(
                [AgentMessage(role="user", content="\n\n".join(source_parts))],
                system_prompt=MEMORY_SUMMARY_SYSTEM_PROMPT,
                tools=[],
            )
        except AgentProviderError:
            return False

        summary = response.content.strip()
        if not summary:
            return False

        update_memory_summary(db, conversation, summary)
        return True
