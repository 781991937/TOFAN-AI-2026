"""Role-scoped tool policy for TOFAN's AI workforce.

The General Manager is the only agent allowed to use manager.* and payments.confirm.
Specialists receive only non-manager tools explicitly listed for their domain.
"""
from .models import AgentRole

SPECIALIST_TOOL_ALLOWLIST: dict[AgentRole, tuple[str, ...]] = {
    AgentRole.ACADEMIC: ("academy.structure", "academy.search", "manager.global_computing_blueprint", "specialist.academic.operations"),
    AgentRole.STUDENT_AFFAIRS: ("academy.structure", "academy.search", "specialist.student_affairs.operations"),
    AgentRole.FINANCE: ("academy.structure", "specialist.finance.operations"),
    AgentRole.CONTENT: ("academy.structure", "academy.search", "specialist.content.operations"),
    AgentRole.ASSESSMENT: ("academy.structure", "academy.search", "specialist.assessment.operations"),
    AgentRole.CERTIFICATES: ("academy.structure", "academy.search", "specialist.certificates.operations"),
    AgentRole.NOTIFICATIONS: ("academy.structure", "specialist.notifications.operations"),
    AgentRole.SECURITY: ("academy.structure", "specialist.security.operations"),
    AgentRole.RESEARCH: ("academy.structure", "academy.search", "manager.global_computing_blueprint", "specialist.research.operations"),
    AgentRole.CAREER: ("academy.structure", "academy.search", "specialist.career.operations"),
    AgentRole.QUALITY: ("academy.structure", "academy.search", "manager.global_computing_blueprint", "specialist.quality.operations"),
    AgentRole.ADMISSIONS: ("academy.structure", "specialist.admissions.operations"),
    AgentRole.OPERATIONS: ("academy.structure", "academy.search", "specialist.operations.operations"),
}

def tools_for_specialist(role: AgentRole) -> tuple[str, ...]:
    if role not in SPECIALIST_TOOL_ALLOWLIST:
        raise ValueError("Role is not a provisionable specialist role.")
    return SPECIALIST_TOOL_ALLOWLIST[role]
