"""Biometric/passkey authentication contract for TOFAN Smart Academy.

The server never stores a fingerprint or face template. The device performs
biometric verification and unlocks a platform credential (passkey/WebAuthn).
Cryptographic WebAuthn verification must be delegated to a standards-compliant
implementation.
"""

from dataclasses import dataclass
from enum import StrEnum


class BiometricType(StrEnum):
    FINGERPRINT = "fingerprint"
    FACE = "face"
    DEVICE_BIOMETRIC = "device_biometric"
    PASSKEY = "passkey"


@dataclass(frozen=True)
class BiometricCredential:
    credential_id: str
    user_id: str
    device_id: str
    biometric_type: BiometricType
    sign_count: int = 0
    enabled: bool = True


class BiometricAuthError(Exception):
    """Base error for biometric/passkey authentication failures."""


class BiometricService:
    """Application boundary for biometric/passkey authentication."""

    def begin_registration(self, user_id: str, device_id: str) -> dict:
        raise NotImplementedError

    def finish_registration(
        self, user_id: str, device_id: str, credential: dict
    ) -> BiometricCredential:
        raise NotImplementedError

    def begin_authentication(self, user_id: str | None = None) -> dict:
        raise NotImplementedError

    def finish_authentication(self, credential: dict, challenge: str) -> str:
        raise NotImplementedError
