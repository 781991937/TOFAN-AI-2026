"""Student onboarding orchestration state for the TOFAN frontend.

This endpoint does not perform verification or grant access. It exposes the
server-authoritative next step so a client cannot decide access locally.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.db.identity_models import PaymentStatus, ProfileStatus, PaymentTransaction, StudentProfile
from app.db.models import BiometricCredentialRecord, Entitlement, TeachingAccess, User

router = APIRouter(prefix="/student/onboarding", tags=["student-onboarding"])


@router.get("")
def get_onboarding_state(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == actor.id))
    if profile is None:
        return {
            "step": "profile",
            "completed": False,
            "status": "pending",
            "next_action": "complete_profile",
            "allowed_actions": ["complete_profile"],
        }

    credentials_count = db.scalar(
        select(BiometricCredentialRecord.id)
        .where(
            BiometricCredentialRecord.user_id == actor.id,
            BiometricCredentialRecord.enabled.is_(True),
        )
        .limit(1)
    )
    payment = db.scalar(
        select(PaymentTransaction)
        .where(PaymentTransaction.user_id == actor.id)
        .order_by(PaymentTransaction.created_at.desc())
    )
    entitlement = db.scalar(
        select(Entitlement).where(
            Entitlement.user_id == actor.id,
            Entitlement.content_file_id.is_(None),
            Entitlement.access_type == TeachingAccess.PAID.value,
        )
    )

    if profile.profile_status == ProfileStatus.BLOCKED:
        step = "blocked"
        next_action = None
        allowed_actions = []
    elif profile.profile_status != ProfileStatus.VERIFIED:
        step = "biometric_registration" if credentials_count is None else "biometric_authentication"
        next_action = (
            "register_passkey" if credentials_count is None else "authenticate_passkey"
        )
        allowed_actions = [next_action]
    elif entitlement is not None:
        step = "curriculum"
        next_action = "open_global_curriculum"
        allowed_actions = ["open_global_curriculum"]
    elif payment is not None and payment.status == PaymentStatus.PENDING:
        step = "owner_approval"
        next_action = "wait_for_owner_confirmation"
        allowed_actions = []
    elif payment is not None and payment.status == PaymentStatus.CONFIRMED:
        step = "access_activation"
        next_action = "refresh_access"
        allowed_actions = ["refresh_access"]
    else:
        step = "payment"
        next_action = "request_global_curriculum"
        allowed_actions = ["request_global_curriculum"]

    return {
        "step": step,
        "completed": entitlement is not None,
        "profile": {
            "id": profile.id,
            "status": profile.profile_status,
            "biometric_verified": profile.biometric_verified,
        },
        "passkey": {
            "registered": credentials_count is not None,
        },
        "payment": None if payment is None else {
            "transaction_id": payment.id,
            "product_key": payment.product_key,
            "status": payment.status,
        },
        "global_curriculum": {
            "entitled": entitlement is not None,
            "access_type": TeachingAccess.PAID.value if entitlement is not None else None,
            "expires_at": entitlement.expires_at if entitlement is not None else None,
        },
        "next_action": next_action,
        "allowed_actions": allowed_actions,
    }
