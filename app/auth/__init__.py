"""Authentication and authorization boundaries for TOFAN Smart Academy."""

from .biometric import (
    BiometricAuthError,
    BiometricCredential,
    BiometricService,
    BiometricType,
)
from .models import RoleName, UserRole
from .service import AuthorizationError, has_role, require_role

__all__ = [
    "AuthorizationError",
    "BiometricAuthError",
    "BiometricCredential",
    "BiometricService",
    "BiometricType",
    "RoleName",
    "UserRole",
    "has_role",
    "require_role",
]
