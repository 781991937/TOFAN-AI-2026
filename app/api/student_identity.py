"""Student onboarding, biometric verification, and global-access payment flow."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.models import Agent, AgentKind
from app.agents.teaching_policy import grant_paid_global_access
from app.agents.payment_tools import confirm_payment_transaction
from app.agents.main_manager import MainManagerService
from app.auth.dependencies import get_current_user, get_db
from app.auth.authorization import require_owner_or_admin
from app.db.identity_models import (
    PaymentStatus,
    PaymentTransaction,
    ProfileStatus,
    StudentProfile,
    UserType,
)
from app.db.models import AcademicUnit, BiometricCredentialRecord, Institution, User, Entitlement, TeachingAccess

router = APIRouter(prefix="/student", tags=["student-identity"])


class ProfileRequest(BaseModel):
    user_type: UserType
    full_name: str = Field(min_length=2, max_length=255)
    age: int | None = Field(default=None, ge=1, le=120)
    institution_id: str | None = None
    college_unit_id: str | None = None
    major_unit_id: str | None = None


class PaymentRequest(BaseModel):
    product_key: str = Field(default="global_curriculum", min_length=2, max_length=100)
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=20)
    reference: str | None = Field(default=None, max_length=255)


class PaymentConfirmation(BaseModel):
    transaction_id: str


def _academic_unit(
    db: Session, unit_id: str | None, institution_id: str, expected_type: str
) -> AcademicUnit:
    if not unit_id:
        raise HTTPException(
            status_code=409,
            detail=f"The {expected_type} is required. If it is not listed, it is currently under construction.",
        )
    unit = db.get(AcademicUnit, unit_id)
    if (
        unit is None
        or not unit.is_active
        or unit.institution_id != institution_id
        or unit.unit_type != expected_type
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"The selected {expected_type} is not currently available. "
                f"The {expected_type} is under construction."
            ),
        )
    return unit


@router.get("/profile")
def get_profile(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == actor.id))
    if profile is None:
        return {"completed": False, "profile": None}
    return {
        "completed": profile.profile_status != ProfileStatus.PENDING,
        "profile": {
            "id": profile.id,
            "user_type": profile.user_type,
            "full_name": profile.full_name,
            "age": profile.age,
            "institution_id": profile.institution_id,
            "college_unit_id": profile.college_unit_id,
            "major_unit_id": profile.major_unit_id,
            "status": profile.profile_status,
            "biometric_verified": profile.biometric_verified,
        },
    }


@router.get("/access")
def get_student_access(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == actor.id))
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
    return {
        "user_id": actor.id,
        "profile": None if profile is None else {
            "user_type": profile.user_type,
            "full_name": profile.full_name,
            "status": profile.profile_status,
            "biometric_verified": profile.biometric_verified,
        },
        "payment": None if payment is None else {
            "transaction_id": payment.id,
            "product_key": payment.product_key,
            "status": payment.status,
            "confirmed_at": payment.confirmed_at,
        },
        "global_curriculum": {
            "entitled": entitlement is not None,
            "access_type": TeachingAccess.PAID.value if entitlement is not None else None,
            "expires_at": entitlement.expires_at if entitlement is not None else None,
        },
        "security_rule": "Access is granted only from server-side confirmed payment state.",
    }


@router.post("/profile")
def create_or_update_profile(
    payload: ProfileRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == actor.id))

    if payload.user_type == UserType.UNIVERSITY_STUDENT:
        if not payload.institution_id:
            raise HTTPException(status_code=409, detail="Select a university to continue.")
        institution = db.get(Institution, payload.institution_id)
        if institution is None or not institution.is_active:
            raise HTTPException(
                status_code=409,
                detail="The selected university is not currently available. "
                       "The university is under construction.",
            )
        _academic_unit(db, payload.college_unit_id, institution.id, "college")
        _academic_unit(db, payload.major_unit_id, institution.id, "major")

    if profile is None:
        profile = StudentProfile(
            user_id=actor.id,
            user_type=payload.user_type,
            full_name=payload.full_name,
            age=payload.age,
            institution_id=payload.institution_id if payload.user_type == UserType.UNIVERSITY_STUDENT else None,
            college_unit_id=payload.college_unit_id if payload.user_type == UserType.UNIVERSITY_STUDENT else None,
            major_unit_id=payload.major_unit_id if payload.user_type == UserType.UNIVERSITY_STUDENT else None,
        )
        db.add(profile)
    else:
        profile.user_type = payload.user_type
        profile.full_name = payload.full_name
        profile.age = payload.age
        profile.institution_id = payload.institution_id if payload.user_type == UserType.UNIVERSITY_STUDENT else None
        profile.college_unit_id = payload.college_unit_id if payload.user_type == UserType.UNIVERSITY_STUDENT else None
        profile.major_unit_id = payload.major_unit_id if payload.user_type == UserType.UNIVERSITY_STUDENT else None
        profile.profile_status = ProfileStatus.PENDING
        profile.biometric_verified = False
        profile.verified_at = None

    db.commit()
    db.refresh(profile)
    return {
        "profile_id": profile.id,
        "status": profile.profile_status,
        "next_step": "biometric_verification",
    }


@router.post("/profile/verify-biometric")
def verify_profile_biometric(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == actor.id))
    if profile is None:
        raise HTTPException(status_code=400, detail="Complete the profile questionnaire first.")

    credential = db.scalar(
        select(BiometricCredentialRecord).where(
            BiometricCredentialRecord.user_id == actor.id,
            BiometricCredentialRecord.enabled.is_(True),
        )
    )
    if credential is None:
        raise HTTPException(
            status_code=409,
            detail="No registered biometric/passkey credential was found for this account.",
        )

    profile.biometric_verified = True
    profile.profile_status = ProfileStatus.VERIFIED
    profile.verified_at = datetime.utcnow()
    db.commit()
    return {
        "profile_id": profile.id,
        "status": profile.profile_status,
        "biometric_verified": True,
    }


@router.post("/payments/request", status_code=201)
def request_payment(
    payload: PaymentRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == actor.id))
    if profile is None or profile.profile_status != ProfileStatus.VERIFIED:
        raise HTTPException(
            status_code=409,
            detail="Complete profile verification before requesting global curriculum access.",
        )

    transaction = PaymentTransaction(
        user_id=actor.id,
        product_key=payload.product_key,
        amount=payload.amount,
        currency=payload.currency,
        reference=payload.reference,
        status=PaymentStatus.PENDING,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return {
        "transaction_id": transaction.id,
        "product_key": transaction.product_key,
        "status": transaction.status,
        "message": "Payment request recorded and awaiting confirmation.",
    }


@router.post("/payments/{transaction_id}/confirm")
def confirm_payment(
    transaction_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    transaction = db.get(PaymentTransaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Payment transaction not found.")
    if transaction.product_key != "global_curriculum":
        raise HTTPException(
            status_code=409,
            detail="This confirmation endpoint is only for global curriculum payments.",
        )

    try:
        result = confirm_payment_transaction(db, transaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    MainManagerService.process_event(
        db,
        "payments.confirmed",
        transaction.user_id,
        {"resource_type": "payment_transaction", "resource_id": transaction_id, "transaction_id": transaction_id},
    )
    return result
