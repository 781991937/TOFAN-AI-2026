"""AI-assisted conversation memory compaction for the TOFAN Main Agent."""

from sqlalchemy.orm import Session

from .memory import (
    AgentConversation,
    AgentMemoryItem,
    AgentMessageRecord,
    active_memory_items,
    update_memory_summary,
    upsert_memory_item,
)
from .providers import AIProvider, AgentMessage, AgentProviderError


MEMORY_RECENT_LIMIT = 12
MEMORY_COMPACTION_THRESHOLD = 20
MEMORY_ITEM_MIN_CONFIDENCE = 0.85

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


MEMORY_FACT_SYSTEM_PROMPT = """You are the TOFAN Academy memory extractor.
Extract only durable facts explicitly stated by the user in the supplied conversation.
Return one JSON array. Each item must contain: type, content, confidence, source_sequence.
Allowed type values: preference, goal, constraint, task, decision.
Do not infer sensitive traits. Do not extract temporary chatter. Do not invent facts.
Confidence must be between 0 and 1. If there are no durable facts, return [].
"""

    
def extract_structured_memory(self, db: Session, conversation: AgentConversation, messages: list[AgentMessageRecord]) -> int:
        if not messages:
            return 0
        source = "\\n".join(f"[{m.sequence}] {m.role}: {m.content}" for m in messages)
        try:
            response = self.provider.generate(
                [AgentMessage(role="user", content=source)],
                system_prompt=MEMORY_FACT_SYSTEM_PROMPT,
                tools=[],
            )
            import json
            items = json.loads(response.content.strip() or "[]")
        except (AgentProviderError, ValueError, json.JSONDecodeError):
            return 0
        if not isinstance(items, list):
            return 0
        count = 0
        for item in items:
            if not isinstance(item, dict) or item.get("type") not in {"preference", "goal", "constraint", "task", "decision"}:
                continue
            confidence = float(item.get("confidence", 0))
            if confidence < MEMORY_ITEM_MIN_CONFIDENCE or not str(item.get("content", "")).strip():
                continue
            upsert_memory_item(
                db, conversation.id, conversation.user_id, item["type"],
                str(item["content"]), confidence, int(item["source_sequence"]) if item.get("source_sequence") else None,
            )
            count += 1
        return count

    def context_for_agent(self, db: Session, conversation: AgentConversation) -> str:
        items = active_memory_items(db, conversation.id)
        if not items:
            return ""
        return "Structured persistent memory:\\n" + "\\n".join(
            f"- [{item.memory_type}] {item.content} (confidence={item.confidence:.2f})" for item in items
        )
