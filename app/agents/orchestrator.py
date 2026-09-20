"""Main Agent orchestration with model-driven tool selection."""

from dataclasses import dataclass
from collections.abc import Callable
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from .llm import build_configured_provider
from .memory import build_memory_context
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
    def __init__(self, runtime: AgentRuntime, service: AgentService,
                 provider: AIProvider | None = None, registry: ToolRegistry | None = None,
                 tool_input_guard: Callable[[Session, Agent, str, dict], None] | None = None) -> None:
        self.runtime, self.service, self.provider, self.registry = runtime, service, provider, registry
        self.tool_input_guard = tool_input_guard

    def decide(self, db: Session, agent: Agent, user_text: str) -> AgentDecision:
        text, lowered = user_text.strip(), user_text.strip().casefold()
        if any(w in lowered for w in ("هيكل", "الهيكل", "الأقسام", "التخصصات", "الكليات", "الجامعة")):
            return AgentDecision("tool", "academy.structure", "", "The request asks about academy structure.")
        if any(w in lowered for w in ("ابحث", "بحث", "مادة", "محاضرة", "محاضرات", "مقرر", "دورة", "وحدة")):
            return AgentDecision("tool", "academy.search", json.dumps({"query": text, "limit": 10}, ensure_ascii=False), "The request looks like an academy content search.")
        return AgentDecision("message", None, "", "No safe deterministic tool route matched the request.")

    def _enabled_tool_names(self, db: Session, agent: Agent) -> list[str]:
        return [n for n in self.registry.names() if db.scalar(select(AgentTool.id).where(
            AgentTool.agent_id == agent.id, AgentTool.tool_name == n, AgentTool.enabled.is_(True)))]

    def _live_model(self, db: Session, agent: Agent, user_text: str, actor_user_id: str | None,
                    history: list[AgentMessage] | None = None, memory_context: str | None = None) -> dict:
        provider = self.provider or build_configured_provider()
        if not self.registry:
            raise AgentProviderError("Tool registry is not configured.")
        enabled = self._enabled_tool_names(db, agent)
        definitions = self.registry.openai_definitions(enabled)
        messages = list(history or [])
        if memory_context:
            messages.insert(0, AgentMessage(role="system", content=memory_context))
        messages.append(AgentMessage(role="user", content=user_text))
        first = provider.generate(messages, system_prompt=agent.system_prompt, tools=definitions)
        if not first.tool_calls:
            return {"kind": "model", "provider": first.provider, "model": first.model, "content": first.content}

        outputs = []
        for call in first.tool_calls:
            try:
                payload = json.loads(call["arguments"] or "{}")
            except json.JSONDecodeError as exc:
                raise AgentProviderError("Model returned invalid tool arguments.") from exc
            if self.tool_input_guard:
                self.tool_input_guard(db, agent, call["name"], payload)
            run = self.runtime.execute_tool(db, agent, call["name"], json.dumps(payload, ensure_ascii=False), actor_user_id=actor_user_id)
            outputs.append({"call_id": call["call_id"], "output": run.output_text})

        if not isinstance(provider, OpenAIResponsesProvider):
            return {"kind": "tool", "provider": first.provider, "model": first.model, "tool_calls": [c["name"] for c in first.tool_calls], "outputs": outputs}

        final = provider.submit_tool_outputs(
            messages=[{"role": m.role, "content": m.content} for m in messages] + [
                {"type": "function_call", "call_id": c["call_id"], "name": c["name"], "arguments": c["arguments"]}
                for c in first.tool_calls
            ],
            tool_outputs=outputs, system_prompt=agent.system_prompt,
        )
        return {"kind": "model_tool", "provider": final.provider, "model": final.model,
                "content": final.content, "tool_calls": [c["name"] for c in first.tool_calls]}

    def run(self, db: Session, agent: Agent, actor_user_id: str | None, user_text: str,
            history: list[AgentMessage] | None = None, memory_context: str | None = None):
        try:
            return self._live_model(db, agent, user_text, actor_user_id, history, memory_context)
        except AgentProviderError:
            decision = self.decide(db, agent, user_text)
            if decision.kind == "message":
                return {"kind": "message", "content": "الوكيل الرئيسي يعمل حاليًا بالوضع الاحتياطي؛ لم يتوفر مزود نموذج مهيأ لهذا الطلب.", "reason": decision.reason}
            tool_run = self.runtime.execute_tool(db, agent, decision.tool_name, decision.tool_input, actor_user_id=actor_user_id)
            return {"kind": "tool", "tool_name": decision.tool_name, "output": tool_run.output_text, "run_id": tool_run.id, "reason": decision.reason}
