"""Role-scoped tool policy for TOFAN's AI workforce.

The General Manager is the only agent allowed to use manager.* and payments.confirm.
Specialists receive only non-manager tools explicitly listed for their domain.
"""
from .models import AgentRole

SPECIALIST_TOOL_ALLOWLIST: dict[AgentRole, tuple[str, ...]] = {
    AgentRole.ACADEMIC: ("academy.structure", "academy.search", "manager.global_computing_blueprint"),
    AgentRole.STUDENT_AFFAIRS: ("academy.structure", "academy.search"),
    AgentRole.FINANCE: ("academy.structure",),
    AgentRole.CONTENT: ("academy.structure", "academy.search"),
    AgentRole.ASSESSMENT: ("academy.structure", "academy.search", "education.assessment_result"),
    AgentRole.CERTIFICATES: ("academy.structure", "academy.search"),
    AgentRole.NOTIFICATIONS: ("academy.structure",),
    AgentRole.SECURITY: ("academy.structure",),
    AgentRole.RESEARCH: ("academy.structure", "academy.search", "manager.global_computing_blueprint"),
    AgentRole.CAREER: ("academy.structure", "academy.search"),
    AgentRole.QUALITY: ("academy.structure", "academy.search", "manager.global_computing_blueprint"),
    AgentRole.ADMISSIONS: ("academy.structure",),
    AgentRole.OPERATIONS: ("academy.structure", "academy.search"),
}

def tools_for_specialist(role: AgentRole) -> tuple[str, ...]:
    if role not in SPECIALIST_TOOL_ALLOWLIST:
        raise ValueError("Role is not a provisionable specialist role.")
    return SPECIALIST_TOOL_ALLOWLIST[role]
