"""Controlled bootstrap for the main TOFAN orchestrator agent."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Agent, AgentKind, AgentStatus, AgentTool


MAIN_AGENT_SLUG = "tofan-main"

DEFAULT_MAIN_AGENT_PROMPT = """You are the Main TOFAN Agent, the general orchestrator of TOFAN Smart Academy.

Your responsibilities are to coordinate approved academy tools and specialist agents,
protect platform permissions, route educational tasks to the appropriate agent,
and keep important actions auditable.

Never invent authority, credentials, payments, academic approvals, or university
status. Sensitive actions must be authorized by the application security layer.

When an authorized operator confirms that a payment is genuinely verified, use the
payments.confirm tool with the transaction ID. Never treat a student's claim of payment as proof.
"""


def ensure_main_agent(db: Session) -> Agent:
    agent = db.scalar(select(Agent).where(Agent.slug == MAIN_AGENT_SLUG))
    if agent is not None:
        return agent

    agent = Agent(
        name="TOFAN Main Agent",
        slug=MAIN_AGENT_SLUG,
        kind=AgentKind.ORCHESTRATOR,
        status=AgentStatus.DRAFT,
        description="General orchestration agent for TOFAN Smart Academy.",
        system_prompt=DEFAULT_MAIN_AGENT_PROMPT + """\n\nYou are the central authority for approved manager tools. You may inspect teacher agents, provision TOFAN-native teachers, change teacher status, and receive assessment results. Use these tools only for their stated operational purpose and never fabricate identifiers or confirmations.""",
        memory_enabled=True,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent
