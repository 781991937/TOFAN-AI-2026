"""Privileged payment confirmation actions for the main TOFAN manager."""

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.models import Agent, AgentKind, AgentStatus
from app.agents.teaching_policy import grant_paid_global_access
from app.db.identity_models import PaymentStatus, PaymentTransaction
from app.db.models import AuditLog, Entitlement, TeachingAccess


def confirm_payment_transaction(db: Session, transaction_id: str) -> dict:
    transaction = db.get(PaymentTransaction, transaction_id)
    if transaction is None:
        raise ValueError("Payment transaction not found.")

    main_agent = db.scalar(
        select(Agent).where(
            Agent.slug == "tofan-main",
            Agent.kind == AgentKind.ORCHESTRATOR,
            Agent.status == AgentStatus.ACTIVE,
        )
    )
    if main_agent is None:
        raise ValueError("Main manager agent is not configured.")

    if transaction.status == PaymentStatus.CONFIRMED:
        return {
            "transaction_id": transaction.id,
            "status": transaction.status.value,
            "global_access": "active",
            "idempotent": True,
        }

    if transaction.status != PaymentStatus.PENDING:
        raise ValueError("Only pending payment transactions can be confirmed.")

    transaction.status = PaymentStatus.CONFIRMED
    transaction.confirmed_by_agent_id = main_agent.id
    transaction.confirmed_at = datetime.utcnow()

    existing = db.scalar(
        select(Entitlement).where(
            Entitlement.user_id == transaction.user_id,
            Entitlement.access_type == TeachingAccess.PAID.value,
            Entitlement.content_file_id.is_(None),
        )
    )
    if existing is None:
        db.add(
            Entitlement(
                user_id=transaction.user_id,
                access_type=TeachingAccess.PAID.value,
            )
        )

    teachers = db.scalars(
        select(Agent).where(
            Agent.kind == AgentKind.TEACHER,
            Agent.status == "active",
        )
    ).all()
    for teacher in teachers:
        grant_paid_global_access(
            db,
            user_id=transaction.user_id,
            agent_id=teacher.id,
        )

    db.add(
        AuditLog(
            user_id=transaction.user_id,
            action="payment.confirmed",
            resource_type="payment_transaction",
            resource_id=transaction.id,
            details=json.dumps(
                {
                    "product_key": transaction.product_key,
                    "confirmed_by_agent_id": main_agent.id,
                    "global_access": "active",
                },
                ensure_ascii=False,
            ),
        )
    )
    db.flush()
    return {
        "transaction_id": transaction.id,
        "status": transaction.status.value,
        "global_access": "active",
        "confirmed_by_agent_id": main_agent.id,
    }


def confirm_payment_tool(db: Session, input_text: str) -> str:
    try:
        payload = json.loads(input_text or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Input must be valid JSON.") from exc
    transaction_id = str(payload.get("transaction_id", "")).strip()
    if not transaction_id:
        raise ValueError("transaction_id is required.")
    return json.dumps(
        confirm_payment_transaction(db, transaction_id),
        ensure_ascii=False,
    )
