"""Contracts for external identity verification."""
from dataclasses import dataclass
from enum import StrEnum
class AuthProvider(StrEnum): GOOGLE="google"; EMAIL="email"; PHONE="phone"; PASSKEY="passkey"
@dataclass(frozen=True)
class VerifiedIdentity:
    provider: AuthProvider
    subject: str
    email: str|None=None
    phone: str|None=None
    display_name: str|None=None
class ProviderVerificationError(ValueError): pass
class GoogleProvider:
    def verify_id_token(self,id_token: str)->VerifiedIdentity: raise NotImplementedError("Connect a standards-compliant OIDC provider adapter.")
class PasskeyProvider:
    def verify_assertion(self,payload: dict)->VerifiedIdentity: raise NotImplementedError("Connect a WebAuthn provider adapter.")
