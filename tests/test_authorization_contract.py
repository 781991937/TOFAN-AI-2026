import pytest
from fastapi import HTTPException

from app.auth.authorization import require_any_role, require_owner_or_admin
from app.auth.models import RoleName


def test_student_is_not_admin_or_owner():
    dependency = require_owner_or_admin.dependency
    with pytest.raises(HTTPException) as exc:
        dependency([RoleName.STUDENT])
    assert exc.value.status_code == 403


def test_admin_can_use_owner_or_admin_gate():
    dependency = require_owner_or_admin.dependency
    assert dependency([RoleName.ADMIN]) == [RoleName.ADMIN]


def test_owner_can_use_owner_or_admin_gate():
    dependency = require_owner_or_admin.dependency
    assert dependency([RoleName.OWNER]) == [RoleName.OWNER]


def test_unrelated_role_is_rejected():
    dependency = require_any_role(RoleName.REVIEWER)
    with pytest.raises(HTTPException) as exc:
        dependency([RoleName.STUDENT])
    assert exc.value.status_code == 403
