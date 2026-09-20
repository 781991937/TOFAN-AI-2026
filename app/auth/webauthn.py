"""WebAuthn/passkey verification for TOFAN Smart Academy.

The browser/device performs biometric verification locally. The server verifies
the WebAuthn challenge, RP ID/origin, user-verification flag, signature, and
signature counter. No biometric template is stored.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fido2.cbor import decode as cbor_decode
from fido2.cbor import encode as cbor_encode
from fido2.server import Fido2Server
from fido2.utils import websafe_decode, websafe_encode
from fido2.webauthn import (
    AttestedCredentialData,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    UserVerificationRequirement,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.biometric import BiometricAuthError, BiometricCredential
from app.db.models import BiometricCredentialRecord, PasskeyChallenge, User

CHALLENGE_TTL_SECONDS = 300


def _settings() -> tuple[str, str]:
    rp_id = os.getenv("WEBAUTHN_RP_ID", "localhost")
    origin = os.getenv("WEBAUTHN_ORIGIN", "http://localhost")
    return rp_id, origin


def _server() -> Fido2Server:
    rp_id, origin = _settings()
    rp = PublicKeyCredentialRpEntity(id=rp_id, name="TOFAN Smart Academy")
    return Fido2Server(rp, verify_origin=lambda value: value == origin)


def _json_default(value: Any) -> Any:
    if isinstance(value, bytes):
        return websafe_encode(value)
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return list(value)
    raise TypeError(f"Unsupported WebAuthn state value: {type(value)!r}")


def _credential_from_record(record: BiometricCredentialRecord) -> AttestedCredentialData:
    try:
        credential_id = websafe_decode(record.credential_id)
        public_key = cbor_decode(websafe_decode(record.public_key))
        from fido2.cose import CoseKey
        cose_key = CoseKey.parse(public_key)
        return AttestedCredentialData.create(b"\\x00" * 16, credential_id, cose_key)
    except Exception as exc:
        raise BiometricAuthError("Stored passkey credential is invalid.") from exc


def _save_challenge(
    db: Session,
    *,
    user_id: str | None,
    purpose: str,
    state: dict,
    device_id: str | None = None,
) -> PasskeyChallenge:
    challenge = PasskeyChallenge(
        user_id=user_id,
        purpose=purpose,
        state_json=json.dumps(state, ensure_ascii=False, default=_json_default),
        device_id=device_id,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=CHALLENGE_TTL_SECONDS),
    )
    db.add(challenge)
    db.flush()
    return challenge


def begin_registration(db: Session, user: User, device_id: str) -> dict:
    existing = db.scalars(
        select(BiometricCredentialRecord).where(
            BiometricCredentialRecord.user_id == user.id,
            BiometricCredentialRecord.enabled.is_(True),
        )
    ).all()
    credentials = [_credential_from_record(item) for item in existing]
    user_entity = PublicKeyCredentialUserEntity(
        id=user.id.encode(),
        name=user.email or user.phone or user.id,
        display_name=user.display_name or user.email or "TOFAN User",
    )
    options, state = _server().register_begin(
        user_entity,
        credentials=credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge = _save_challenge(
        db,
        user_id=user.id,
        purpose="registration",
        state=state,
        device_id=device_id,
    )
    return {"challenge_id": challenge.id, "options": dict(options)}


def finish_registration(
    db: Session,
    user: User,
    device_id: str,
    challenge_id: str,
    response: dict,
) -> BiometricCredential:
    challenge = db.get(PasskeyChallenge, challenge_id)
    if (
        challenge is None
        or challenge.user_id != user.id
        or challenge.purpose != "registration"
        or challenge.consumed_at is not None
        or challenge.expires_at < datetime.now(timezone.utc)
    ):
        raise BiometricAuthError("Registration challenge is invalid or expired.")

    state = json.loads(challenge.state_json)
    try:
        auth_data = _server().register_complete(state, response)
    except Exception as exc:
        raise BiometricAuthError("Passkey registration verification failed.") from exc

    credential_data = auth_data.credential_data
    assert credential_data is not None

    credential_id = websafe_encode(credential_data.credential_id)
    public_key = websafe_encode(cbor_encode(credential_data.public_key))
    record = BiometricCredentialRecord(
        user_id=user.id,
        device_id=device_id,
        credential_id=credential_id,
        public_key=public_key,
        sign_count=auth_data.sign_count,
        enabled=True,
    )
    db.add(record)
    challenge.consumed_at = datetime.utcnow()
    db.flush()
    return BiometricCredential(
        credential_id=credential_id,
        user_id=user.id,
        device_id=device_id,
        biometric_type="passkey",
        sign_count=auth_data.sign_count,
        enabled=True,
    )


def begin_authentication(db: Session, user: User) -> dict:
    records = db.scalars(
        select(BiometricCredentialRecord).where(
            BiometricCredentialRecord.user_id == user.id,
            BiometricCredentialRecord.enabled.is_(True),
        )
    ).all()
    if not records:
        raise BiometricAuthError("No registered passkey was found.")

    credentials = [_credential_from_record(item) for item in records]
    options, state = _server().authenticate_begin(
        credentials=credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge = _save_challenge(
        db,
        user_id=user.id,
        purpose="authentication",
        state=state,
    )
    return {"challenge_id": challenge.id, "options": dict(options)}


def finish_authentication(
    db: Session,
    user: User,
    challenge_id: str,
    response: dict,
) -> BiometricCredential:
    challenge = db.get(PasskeyChallenge, challenge_id)
    if (
        challenge is None
        or challenge.user_id != user.id
        or challenge.purpose != "authentication"
        or challenge.consumed_at is not None
        or challenge.expires_at < datetime.now(timezone.utc)
    ):
        raise BiometricAuthError("Authentication challenge is invalid or expired.")

    records = db.scalars(
        select(BiometricCredentialRecord).where(
            BiometricCredentialRecord.user_id == user.id,
            BiometricCredentialRecord.enabled.is_(True),
        )
    ).all()
    credentials = [_credential_from_record(item) for item in records]
    state = json.loads(challenge.state_json)

    try:
        verified = _server().authenticate_complete(state, credentials, response)
    except Exception as exc:
        raise BiometricAuthError("Passkey authentication verification failed.") from exc

    credential_id = websafe_encode(verified.credential_id)
    record = next((item for item in records if item.credential_id == credential_id), None)
    if record is None:
        raise BiometricAuthError("Authenticated credential is not registered to this user.")

    from fido2.webauthn import AuthenticationResponse
    parsed = AuthenticationResponse.from_dict(response)
    new_sign_count = parsed.response.authenticator_data.sign_count
    if new_sign_count and new_sign_count <= record.sign_count:
        raise BiometricAuthError("Passkey signature counter did not advance; possible credential clone.")
    record.sign_count = max(record.sign_count, new_sign_count)
    record.last_used_at = datetime.utcnow()
    challenge.consumed_at = datetime.utcnow()
    db.flush()

    return BiometricCredential(
        credential_id=record.credential_id,
        user_id=user.id,
        device_id=record.device_id,
        biometric_type="passkey",
        sign_count=record.sign_count,
        enabled=record.enabled,
    )
