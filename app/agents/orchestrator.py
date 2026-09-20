"""Main Agent orchestration with model-driven tool selection."""

from dataclasses import dataclass
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from .llm import build_configured_provider
from .models import Agent, AgentTool
from .providers import AgentMessage, AgentProviderError, AIProvider, OpenAIResponsesProvider
from .runtime import AgentRuntime
from .service import AgentService
from .tools import ToolRegistry


@dataclass(frozen=True)
class AgentDecision:
    kind: str
    tool_name: str | None
    tool_input: str
    reason: str


class MainAgentOrchestrator:
    def __init__(
        self,
        runtime: AgentRuntime,
        service: AgentService,
        provider: AIProvider | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.runtime = runtime
        self.service = service
        self.provider = provider
        self.registry = registry

    def decide(self, db: Session, agent: Agent, user_text: str) -> AgentDecision:
        text = user_text.strip()
        lowered = text.casefold()
        if any(word in lowered for word in ("هيكل", "الهيكل", "الأقسام", "التخصصات", "الكليات", "الجامعة")):
            return AgentDecision("tool", "academy.structure", "", "The request asks about academy structure.")
        if any(word in lowered for word in ("ابحث", "بحث", "مادة", "محاضرة", "محاضرات", "مقرر", "دورة", "وحدة")):
            return AgentDecision(
                "tool", "academy.search",
                json.dumps({"query": text, "limit": 10}, ensure_ascii=False),
                "The request looks like an academy content search.",
            )
        return AgentDecision("message", None, "", "No safe deterministic tool route matched the request.")

    def _enabled_tool_names(self, db: Session, agent: Agent) -> list[str]:
        return [
            name
            for name in self.registry.names()
            if db.scalar(
                select(AgentTool.id).where(
                    AgentTool.agent_id == agent.id,
                    AgentTool.tool_name == name,
                    AgentTool.enabled.is_(True),
                )
            )
        ]

    def _live_model(self, db: Session, agent: Agent, user_text: str, actor_user_id: str | None) -> dict:
        provider = self.provider or build_configured_provider()
        if not self.registry:
            raise AgentProviderError("Tool registry is not configured.")

        enabled_names = self._enabled_tool_names(db, agent)
        definitions = self.registry.openai_definitions(enabled_names)
        first = provider.generate(
            [AgentMessage(role="user", content=user_text)],
            system_prompt=agent.system_prompt,
            tools=definitions,
        )

        if not first.tool_calls:
            return {
                "kind": "model",
                "provider": first.provider,
                "model": first.model,
                "content": first.content,
            }

        tool_outputs = []
        for call in first.tool_calls:
            tool_name = call["name"]
            arguments = call["arguments"]
            try:
                payload = json.loads(arguments or "{}")
            except json.JSONDecodeError as exc:
                raise AgentProviderError("Model returned invalid tool arguments.") from exc

            tool_input = json.dumps(payload, ensure_ascii=False)
            run = self.runtime.execute_tool(
                db, agent, tool_name, tool_input, actor_user_id=actor_user_id
            )
            tool_outputs.append({"call_id": call["call_id"], "output": run.output_text})

        if not isinstance(provider, OpenAIResponsesProvider):
            return {
                "kind": "tool",
                "provider": first.provider,
                "model": first.model,
                "tool_calls": [c["name"] for c in first.tool_calls],
                "outputs": tool_outputs,
            }

        final = provider.submit_tool_outputs(
            messages=[
                {"role": "user", "content": user_text},
                *[
                    {
                        "type": "function_call",
                        "call_id": call["call_id"],
                        "name": call["name"],
                        "arguments": call["arguments"],
                    }
                    for call in first.tool_calls
                ],
            ],
            tool_outputs=tool_outputs,
            system_prompt=agent.system_prompt,
        )
        return {
            "kind": "model_tool",
            "provider": final.provider,
            "model": final.model,
            "content": final.content,
            "tool_calls": [c["name"] for c in first.tool_calls],
        }

    def run(self, db: Session, agent: Agent, actor_user_id: str | None, user_text: str):
        try:
            return self._live_model(db, agent, user_text, actor_user_id)
        except AgentProviderError:
            decision = self.decide(db, agent, user_text)
            if decision.kind == "message":
                return {
                    "kind": "message",
                    "content": "الوكيل الرئيسي يعمل حاليًا بالوضع الاحتياطي؛ لم يتوفر مزود نموذج مهيأ لهذا الطلب.",
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
