
def test_every_specialist_policy_has_fixed_domain_operational_tool():
    for role, tools in SPECIALIST_TOOL_ALLOWLIST.items():
        assert f"specialist.{role.value}.operations" in tools


def test_specialist_operational_tools_are_registered_and_non_sensitive():
    registry = build_default_registry()
    for role in SPECIALIST_TOOL_ALLOWLIST:
        tool = registry.get(f"specialist.{role.value}.operations")
        assert tool.sensitive is False
        assert tool.allowed_agent_slug is None


"""Tests for TOFAN AI workforce roles and tool boundaries."""

from app.agents.models import AgentKind, AgentRole, AgentStatus
from app.agents.tools import build_default_registry
from app.agents.workforce_policy import SPECIALIST_TOOL_ALLOWLIST
from app.agents.tools import build_default_registry, tools_for_specialist


def test_workforce_roles_are_explicit():
    assert AgentRole.GENERAL_MANAGER.value == "general_manager"
    assert AgentRole.TEACHER.value == "teacher"
    assert AgentKind.SPECIALIST.value == "specialist"
    assert AgentStatus.ACTIVE.value == "active"


def test_every_specialist_role_has_a_tool_policy():
    roles = {r for r in AgentRole if r not in {AgentRole.GENERAL_MANAGER, AgentRole.TEACHER}}
    assert set(SPECIALIST_TOOL_ALLOWLIST) == roles
    for role in roles:
        assert tools_for_specialist(role)


def test_specialists_cannot_receive_manager_write_tools():
    manager_tools = {
        "manager.provision_teacher",
        "manager.provision_specialist",
        "manager.delegate_specialist",
        "manager.create_curriculum",
        "manager.create_specialty",
        "manager.create_stage",
        "manager.create_course",
        "manager.create_unit",
        "manager.create_lesson",
        "payments.confirm",
    }
    for tools in SPECIALIST_TOOL_ALLOWLIST.values():
        assert not manager_tools.intersection(tools)


def test_manager_only_tools_remain_restricted_to_main_agent():
    registry = build_default_registry()
    for name in (
        "manager.provision_teacher",
        "manager.provision_specialist",
        "manager.delegate_specialist",
        "payments.confirm",
    ):
        assert registry.get(name).allowed_agent_slug == "tofan-main"


def test_specialist_policy_uses_registered_tools():
    registry = build_default_registry()
    for names in SPECIALIST_TOOL_ALLOWLIST.values():
        for name in names:
            assert name in registry.names()


def test_bulk_teacher_provisioning_is_manager_only():
    registry = build_default_registry()
    tool = registry.get("manager.provision_all_teachers")
    assert tool.allowed_agent_slug == "tofan-main"
    assert tool.sensitive is True
