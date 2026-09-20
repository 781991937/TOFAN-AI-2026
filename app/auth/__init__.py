"""Authentication and authorization boundaries for TOFAN Smart Academy."""

from .biometric import (
    BiometricAuthError,
    BiometricCredential,
    BiometricService,
    BiometricType,
)
from .models import RoleName, UserRole
from .authentication import AuthenticationError, find_or_create_identity, login_email, register_email
from .providers import AuthProvider, VerifiedIdentity
from .service import AuthorizationError, has_role, require_role

__all__ = [
    "AuthorizationError",
    "AuthenticationError",
    "AuthProvider",
    "VerifiedIdentity",
    "find_or_create_identity",
    "login_email",
    "register_email",
    "BiometricAuthError",
    "BiometricCredential",
    "BiometricService",
    "BiometricType",
    "RoleName",
    "UserRole",
    "has_role",
    "require_role",
]
