"""Main Agent orchestration layer with live-provider fallback."""

from dataclasses import dataclass
import json

from sqlalchemy.orm import Session

from .llm import build_configured_provider
from .models import Agent
from .providers import AgentMessage, AgentProviderError, AIProvider
from .runtime import AgentRuntime
from .service import AgentService


@dataclass(frozen=True)
class AgentDecision:
    kind: str
    tool_name: str | None
    tool_input: str
    reason: str


class MainAgentOrchestrator:
    def __init__(self, runtime: AgentRuntime, service: AgentService, provider: AIProvider | None = None) -> None:
        self.runtime = runtime
        self.service = service
        self.provider = provider

    def decide(self, db: Session, agent: Agent, user_text: str) -> AgentDecision:
        text = user_text.strip()
        lowered = text.casefold()

        if any(word in lowered for word in ("هيكل", "الهيكل", "الأقسام", "التخصصات", "الكليات", "الجامعة")):
            return AgentDecision("tool", "academy.structure", "", "The request asks about academy structure.")

        if any(word in lowered for word in ("ابحث", "بحث", "مادة", "محاضرة", "محاضرات", "مقرر", "دورة", "وحدة")):
            return AgentDecision(
                "tool",
                "academy.search",
                json.dumps({"query": text, "limit": 10}, ensure_ascii=False),
                "The request looks like an academy content search.",
            )

        return AgentDecision("message", None, "", "No safe deterministic tool route matched the request.")

    def _live_response(self, agent: Agent, user_text: str) -> dict:
        provider = self.provider or build_configured_provider()
        response = provider.generate(
            [AgentMessage(role="user", content=user_text)],
            system_prompt=agent.system_prompt,
        )
        return {
            "kind": "model",
            "provider": response.provider,
            "model": response.model,
            "content": response.content,
        }

    def run(self, db: Session, agent: Agent, actor_user_id: str | None, user_text: str):
        decision = self.decide(db, agent, user_text)

        if decision.kind == "message":
            try:
                return self._live_response(agent, user_text)
            except AgentProviderError:
                return {
                    "kind": "message",
                    "content": (
                        "لم أجد أداة آمنة ومناسبة لهذا الطلب، ومزود الذكاء الاصطناعي "
                        "غير مهيأ حاليًا. اضبط OPENAI_API_KEY لتفعيل الوكيل الرئيسي."
                    ),
                    "reason": decision.reason,
                }

        tool_run = self.runtime.execute_tool(
            db, agent, decision.tool_name, decision.tool_input, actor_user_id=actor_user_id
        )
        return {
            "kind": "tool",
            "tool_name": decision.tool_name,
            "output": tool_run.output_text,
            "run_id": tool_run.id,
            "reason": decision.reason,
        }
