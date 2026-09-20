"""AI-assisted conversation memory for the TOFAN Main Agent."""

import json

from sqlalchemy.orm import Session

from .memory import (
    AgentConversation,
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
Create a compact factual summary of durable information explicitly established
in the supplied conversation. Keep preferences, goals, constraints, decisions,
and unresolved tasks. Do not invent facts or infer sensitive traits.
Return only the summary in concise plain text.
"""

MEMORY_FACT_SYSTEM_PROMPT = """You are the TOFAN Academy memory extractor.
Extract only durable facts explicitly stated by the user.
Return one JSON array. Each item must contain:
type, content, confidence, source_sequence.
Allowed type values: preference, goal, constraint, task, decision.
Do not infer sensitive traits or invent facts. Confidence must be 0..1.
Return [] when there are no durable facts.
"""


class ConversationMemoryService:
    """Maintains compact and structured persistent memory."""

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
            "Older conversation:\n"
            + "\n".join(f"[{m.sequence}] {m.role}: {m.content}" for m in older)
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

    def extract_structured_memory(
        self,
        db: Session,
        conversation: AgentConversation,
        messages: list[AgentMessageRecord],
    ) -> int:
        if not messages:
            return 0
        source = "\n".join(f"[{m.sequence}] {m.role}: {m.content}" for m in messages)
        try:
            response = self.provider.generate(
                [AgentMessage(role="user", content=source)],
                system_prompt=MEMORY_FACT_SYSTEM_PROMPT,
                tools=[],
            )
            items = json.loads(response.content.strip() or "[]")
        except (AgentProviderError, ValueError, json.JSONDecodeError):
            return 0
        if not isinstance(items, list):
            return 0

        count = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            memory_type = item.get("type")
            if memory_type not in {"preference", "goal", "constraint", "task", "decision"}:
                continue
            content = str(item.get("content", "")).strip()
            try:
                confidence = float(item.get("confidence", 0))
            except (TypeError, ValueError):
                continue
            if not content or confidence < MEMORY_ITEM_MIN_CONFIDENCE:
                continue
            source_sequence = item.get("source_sequence")
            try:
                source_sequence = int(source_sequence) if source_sequence is not None else None
            except (TypeError, ValueError):
                source_sequence = None
            upsert_memory_item(
                db,
                conversation.id,
                conversation.user_id,
                memory_type,
                content,
                confidence,
                source_sequence,
            )
            count += 1
        return count

    def context_for_agent(self, db: Session, conversation: AgentConversation) -> str:
        items = active_memory_items(db, conversation.id)
        if not items:
            return ""
        return "Structured persistent memory:\n" + "\n".join(
            f"- [{item.memory_type}] {item.content} (confidence={item.confidence:.2f})"
            for item in items
        )
