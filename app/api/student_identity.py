"""Student onboarding, biometric verification, and global-access payment flow."""

from datetime import datetime
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.models import Agent, AgentKind
from app.agents.teaching_policy import grant_paid_global_access
from app.agents.payment_tools import confirm_payment_transaction
from app.agents.academy_access_policy import course_access_tier, has_academy_content_access
from app.agents.main_manager import MainManagerService
from app.auth.dependencies import get_current_user, get_db, get_current_roles
from app.auth.authorization import require_owner_or_admin
from app.auth.models import RoleName
from app.auth.service import has_role
from app.auth.webauthn import begin_authentication, begin_registration, finish_authentication, finish_registration
from app.auth.biometric import BiometricAuthError
from app.db.identity_models import (
    PaymentStatus,
    PaymentTransaction,
    PaymentAccountSetting,
    ProfileStatus,
    StudentProfile,
    UserType,
)
from app.db.models import AcademicUnit, AcademicPeriod, BiometricCredentialRecord, Institution, User, Entitlement, TeachingAccess, Course, Unit, Lecture, ContentFile, ContentStatus, TeachingSource, AuditLog
from app.db.curriculum_models import CurriculumEntitlement, CurriculumStage
from app.storage import get_storage

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


class PaymentRejection(BaseModel):
    reason: str | None = Field(default=None, max_length=500)

class PaymentAccountRequest(BaseModel):
    provider_name: str = Field(min_length=2, max_length=100)
    account_name: str | None = Field(default=None, max_length=255)
    account_number: str = Field(min_length=3, max_length=100)
    instructions: str | None = Field(default=None, max_length=1000)
    currency: str | None = Field(default=None, max_length=20)
    active: bool = True
    amount: float | None = Field(default=None, ge=0)


class PasskeyRegistrationRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=255)
    response: dict


class PasskeyAuthenticationRequest(BaseModel):
    challenge_id: str
    response: dict


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


@router.get("/academy/catalog")
def get_academy_catalog(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == actor.id))
    if profile is None or profile.profile_status != ProfileStatus.VERIFIED:
        raise HTTPException(status_code=403, detail="Complete and verify the student profile first.")

    if profile.user_type != UserType.UNIVERSITY_STUDENT:
        return {
            "scope": "global",
            "message": "Independent learners use the TOFAN global curriculum.",
            "courses": [],
        }

    if not profile.major_unit_id:
        raise HTTPException(status_code=409, detail="Specialization is required before opening academy courses.")

    courses = db.scalars(
        select(Course).where(
            Course.academic_unit_id == profile.major_unit_id,
            Course.is_active.is_(True),
        ).order_by(Course.name)
    ).all()

    result = []
    for course in courses:
        tier = course_access_tier(db, course.id).value
        units = db.scalars(select(Unit).where(Unit.course_id == course.id).order_by(Unit.position)).all()
        lectures = []
        for unit in units:
            rows = db.scalars(select(Lecture).where(Lecture.unit_id == unit.id).order_by(Lecture.position)).all()
            for lecture in rows:
                files = db.scalars(select(ContentFile).where(
                    ContentFile.lecture_id == lecture.id,
                    ContentFile.teaching_source == TeachingSource.GLOBAL_CURRICULUM,
                ).order_by(ContentFile.uploaded_at)).all()
                file_items = []
                for content in files:
                    published = content.status in (ContentStatus.FREE, ContentStatus.PAID)
                    accessible = has_academy_content_access(db, user_id=actor.id, content_file_id=content.id) if published else False
                    file_items.append({
                        "id": content.id,
                        "name": content.original_name,
                        "status": content.status,
                        "accessible": accessible,
                    })
                lectures.append({
                    "id": lecture.id,
                    "title": lecture.title,
                    "position": lecture.position,
                    "status": lecture.status,
                    "accessible": any(item["accessible"] for item in file_items),
                    "files": file_items,
                })

        period = db.get(AcademicPeriod, course.academic_period_id) if course.academic_period_id else None
        result.append({
            "id": course.id,
            "code": course.code,
            "name": course.name,
            "description": course.description,
            "access_tier": tier,
            "year_number": None if period is None else period.year_number,
            "term_number": None if period is None else period.term_number,
            "lectures": lectures,
        })

    return {
        "scope": "academy",
        "institution_id": profile.institution_id,
        "college_unit_id": profile.college_unit_id,
        "major_unit_id": profile.major_unit_id,
        "courses": result,
    }


@router.get("/access/status")
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
    curriculum_entitlement = db.scalar(
        select(CurriculumEntitlement)
        .where(
            CurriculumEntitlement.user_id == actor.id,
            CurriculumEntitlement.active.is_(True),
        )
        .order_by(CurriculumEntitlement.granted_at.desc())
    )
    global_entitlement = db.scalar(
        select(Entitlement).where(
            Entitlement.user_id == actor.id,
            Entitlement.content_file_id.is_(None),
            Entitlement.access_type == TeachingAccess.PAID.value,
        )
    )
    stage = db.get(CurriculumStage, curriculum_entitlement.stage_id) if curriculum_entitlement else None
    entitled = curriculum_entitlement is not None or global_entitlement is not None
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
            "rejection_reason": payment.rejection_reason,
        },
        "global_curriculum": {
            "entitled": entitled,
            "access_type": "curriculum_stage" if curriculum_entitlement else (TeachingAccess.PAID.value if global_entitlement else None),
            "stage_id": curriculum_entitlement.stage_id if curriculum_entitlement else None,
            "stage_name": stage.name if stage else None,
            "expires_at": curriculum_entitlement.expires_at if curriculum_entitlement else (global_entitlement.expires_at if global_entitlement else None),
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


@router.post("/profile/passkey/register/options")
def passkey_register_options(
    device_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == actor.id))
    if profile is None:
        raise HTTPException(status_code=400, detail="Complete the profile questionnaire first.")
    try:
        result = begin_registration(db, actor, device_id)
        db.commit()
        return result
    except BiometricAuthError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/profile/passkey/register/complete")
def passkey_register_complete(
    payload: PasskeyRegistrationRequest,
    challenge_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    try:
        credential = finish_registration(
            db, actor, payload.device_id, challenge_id, payload.response
        )
        db.commit()
        return {
            "registered": True,
            "credential_id": credential.credential_id,
            "next_step": "passkey_authentication",
        }
    except BiometricAuthError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/profile/passkey/authenticate/options")
def passkey_authenticate_options(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    try:
        result = begin_authentication(db, actor)
        db.commit()
        return result
    except BiometricAuthError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/profile/passkey/authenticate/complete")
def passkey_authenticate_complete(
    payload: PasskeyAuthenticationRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == actor.id))
    if profile is None:
        raise HTTPException(status_code=400, detail="Complete the profile questionnaire first.")

    try:
        credential = finish_authentication(
            db, actor, payload.challenge_id, payload.response
        )
        profile.biometric_verified = True
        profile.profile_status = ProfileStatus.VERIFIED
        profile.verified_at = datetime.utcnow()
        db.commit()
        return {
            "verified": True,
            "profile_id": profile.id,
            "status": profile.profile_status,
            "biometric_verified": True,
            "credential_id": credential.credential_id,
        }
    except BiometricAuthError as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/profile/verify-biometric")
def verify_profile_biometric_legacy(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=409,
        detail="Biometric verification now requires a verified WebAuthn/passkey assertion.",
    )


@router.get("/payments/account")
def get_payment_account(db: Session = Depends(get_db)):
    account = db.scalar(
        select(PaymentAccountSetting).where(PaymentAccountSetting.active.is_(True))
        .order_by(PaymentAccountSetting.updated_at.desc())
    )
    if account is None:
        return {"configured": False}
    return {
        "configured": True,
        "provider_name": account.provider_name,
        "account_name": account.account_name,
        "account_number": account.account_number,
        "instructions": account.instructions,
        "currency": account.currency,
        "amount": account.amount,
    }


@router.put("/payments/account")
def configure_payment_account(
    payload: PaymentAccountRequest,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    rows = db.scalars(select(PaymentAccountSetting)).all()
    for row in rows:
        row.active = False
    account = PaymentAccountSetting(**payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return {
        "configured": True,
        "provider_name": account.provider_name,
        "account_name": account.account_name,
        "account_number": account.account_number,
        "instructions": account.instructions,
        "currency": account.currency,
        "amount": account.amount,
        "active": account.active,
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

    if payload.product_key.startswith("curriculum_stage:"):
        stage_id = payload.product_key.split(":", 1)[1].strip()
        if not stage_id:
            raise HTTPException(status_code=400, detail="A curriculum stage is required.")
        from app.db.curriculum_models import CurriculumStage
        stage = db.get(CurriculumStage, stage_id)
        if stage is None:
            raise HTTPException(status_code=404, detail="Curriculum stage not found.")
        if stage.position == 1:
            raise HTTPException(status_code=409, detail="The first semester is free.")
        account = db.scalar(select(PaymentAccountSetting).where(PaymentAccountSetting.active.is_(True)).order_by(PaymentAccountSetting.updated_at.desc()))
        if account is None:
            raise HTTPException(status_code=503, detail="Payment account is not configured yet.")
        if account.amount is None or account.amount <= 0:
            raise HTTPException(status_code=503, detail="Payment amount is not configured yet.")
        payload.amount = account.amount
        payload.currency = account.currency

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
        "amount": transaction.amount,
        "currency": transaction.currency,
        "reference": transaction.reference,
        "proof_file_id": transaction.proof_file_id,
        "message": "Payment request recorded and awaiting confirmation.",
    }


@router.post("/payments/{transaction_id}/proof", status_code=201)
async def upload_payment_proof(
    transaction_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    transaction = db.get(PaymentTransaction, transaction_id)
    if transaction is None or transaction.user_id != actor.id:
        raise HTTPException(status_code=404, detail="Payment transaction not found.")
    if transaction.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=409, detail="Only pending payments can receive a proof.")
    filename = (file.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
    if suffix not in allowed:
        raise HTTPException(status_code=415, detail="Proof must be JPG, PNG, WEBP, or PDF.")
    data = await file.read()
    max_bytes = int(os.getenv("MAX_PAYMENT_PROOF_MB", "10")) * 1024 * 1024
    if not data:
        raise HTTPException(status_code=400, detail="The proof file is empty.")
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="The payment proof exceeds the allowed size.")
    storage = get_storage()
    stored = storage.put_bytes(data, suffix=suffix, prefix=f"{actor.id}/payment-proofs")
    proof = ContentFile(
        original_name=filename,
        storage_key=stored.key,
        mime_type=file.content_type,
        status=ContentStatus.PRIVATE,
        size_bytes=len(data),
        uploaded_by_user_id=actor.id,
        teaching_source=TeachingSource.STUDENT_FILES,
    )
    db.add(proof)
    db.flush()
    transaction.proof_file_id = proof.id
    db.commit()
    return {"transaction_id": transaction.id, "proof_file_id": proof.id, "proof_name": proof.original_name}

@router.get("/payments/{transaction_id}/proof")
def get_payment_proof(
    transaction_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    roles=Depends(get_current_roles),
):
    transaction = db.get(PaymentTransaction, transaction_id)
    if transaction is None or not (transaction.user_id == actor.id or has_role(roles, RoleName.OWNER) or has_role(roles, RoleName.ADMIN)):
        raise HTTPException(status_code=404, detail="Payment proof not found.")
    if not transaction.proof_file_id:
        raise HTTPException(status_code=404, detail="Payment proof not uploaded.")
    proof = db.get(ContentFile, transaction.proof_file_id)
    if proof is None:
        raise HTTPException(status_code=404, detail="Payment proof file not found.")
    try:
        data = get_storage().read_bytes(proof.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Payment proof file not found.")
    return Response(content=data, media_type=proof.mime_type, headers={
        "Content-Disposition": f'attachment; filename="{proof.original_name}"'
    })

@router.post("/payments/{transaction_id}/confirm")
def confirm_payment(
    transaction_id: str,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    transaction = db.get(PaymentTransaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Payment transaction not found.")
    if not (
        transaction.product_key == "global_curriculum"
        or transaction.product_key.startswith("academy_course:")
        or transaction.product_key.startswith("curriculum_stage:")
    ):
        raise HTTPException(
            status_code=409,
            detail="Unsupported payment product.",
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


@router.post("/payments/{transaction_id}/reject")
def reject_payment(
    transaction_id: str,
    payload: PaymentRejection,
    db: Session = Depends(get_db),
    _: list = Depends(require_owner_or_admin),
):
    transaction = db.get(PaymentTransaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Payment transaction not found.")
    if transaction.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=409, detail="Only pending payment transactions can be rejected.")
    transaction.status = PaymentStatus.REJECTED
    transaction.rejection_reason = payload.reason
    db.add(AuditLog(
        user_id=transaction.user_id,
        action="payment.rejected",
        resource_type="payment_transaction",
        resource_id=transaction.id,
        details=payload.reason or "Payment rejected by administrator.",
    ))
    MainManagerService.process_event(
        db,
        "payments.rejected",
        transaction.user_id,
        {"resource_type": "payment_transaction", "resource_id": transaction.id, "transaction_id": transaction.id, "reason": payload.reason},
    )
    db.commit()
    return {
        "transaction_id": transaction.id,
        "status": transaction.status,
        "reason": transaction.rejection_reason,
    }
