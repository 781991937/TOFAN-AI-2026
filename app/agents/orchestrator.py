"""Main Agent orchestration layer.

This layer owns intent routing and keeps model/provider details separate from
academy tools. The first version uses deterministic routing so the academy is
usable before a paid/external model provider is configured.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .models import Agent
from .runtime import AgentRuntime
from .service import AgentService


@dataclass(frozen=True)
class AgentDecision:
    kind: str
    tool_name: str | None
    tool_input: str
    reason: str


class MainAgentOrchestrator:
    def __init__(self, runtime: AgentRuntime, service: AgentService) -> None:
        self.runtime = runtime
        self.service = service

    def decide(self, db: Session, agent: Agent, user_text: str) -> AgentDecision:
        text = user_text.strip()
        lowered = text.casefold()

        if any(word in lowered for word in ("هيكل", "الهيكل", "الأقسام", "التخصصات", "الكليات", "الجامعة")):
            return AgentDecision(
                kind="tool",
                tool_name="academy.structure",
                tool_input="",
                reason="The request asks about academy structure.",
            )

        if any(word in lowered for word in ("ابحث", "بحث", "مادة", "محاضرة", "محاضرات", "مقرر", "دورة", "وحدة")):
            import json

            return AgentDecision(
                kind="tool",
                tool_name="academy.search",
                tool_input=json.dumps({"query": text, "limit": 10}, ensure_ascii=False),
                reason="The request looks like an academy content search.",
            )

        return AgentDecision(
            kind="message",
            tool_name=None,
            tool_input="",
            reason="No safe deterministic tool route matched the request.",
        )

    def run(self, db: Session, agent: Agent, actor_user_id: str | None, user_text: str):
        decision = self.decide(db, agent, user_text)

        if decision.kind == "message":
            return {
                "kind": "message",
                "content": (
                    "لم أجد أداة آمنة ومناسبة لهذا الطلب بعد. "
                    "سيتم ربط نموذج الذكاء الاصطناعي لاحقًا ليحلل الطلب ويختار الأداة المناسبة."
                ),
                "reason": decision.reason,
            }

        run = self.runtime.execute_tool(
            db,
            agent,
            decision.tool_name,
            decision.tool_input,
            actor_user_id=actor_user_id,
        )
        return {
            "kind": "tool",
            "tool_name": decision.tool_name,
            "output": run.output_text,
            "run_id": run.id,
            "reason": decision.reason,
        }
