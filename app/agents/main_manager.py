"""Central authority service for TOFAN's main manager agent.

The main manager is the system authority for payments, assessment reports,
student progress, and teacher-agent oversight. It never trusts client claims.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.models import Agent, AgentKind, AgentStatus, AgentRun
from app.db.assessment_models import CurriculumAssessmentAttempt
from app.db.identity_models import PaymentTransaction, PaymentStatus
from app.db.models import TeachingStep, TeachingStepStatus, TeachingSource, User


class MainManagerService:
    SLUG = "tofan-main"

    @staticmethod
    def get_manager(db: Session) -> Agent:
        manager = db.scalar(select(Agent).where(
            Agent.slug == MainManagerService.SLUG,
            Agent.kind == AgentKind.ORCHESTRATOR,
            Agent.status == AgentStatus.ACTIVE,
        ))
        if manager is None:
            raise RuntimeError("TOFAN main manager agent is not active.")
        return manager

    @staticmethod
    def record_event(
        db: Session,
        *,
        event_name: str,
        actor_user_id: str | None,
        payload: dict,
    ) -> AgentRun:
        manager = MainManagerService.get_manager(db)
        run = AgentRun(
            agent_id=manager.id,
            actor_user_id=actor_user_id,
            tool_name=event_name,
            status="completed",
            input_text=json.dumps(payload, ensure_ascii=False),
            output_text=json.dumps({"accepted": True, "event": event_name}, ensure_ascii=False),
            completed_at=datetime.utcnow(),
        )
        db.add(run)
        return run

    @staticmethod
    def receive_assessment_result(db: Session, attempt_id: str) -> dict:
        attempt = db.get(CurriculumAssessmentAttempt, attempt_id)
        if attempt is None:
            raise ValueError("Assessment attempt not found.")
        MainManagerService.record_event(
            db,
            event_name="education.curriculum_assessment_result",
            actor_user_id=attempt.user_id,
            payload={
                "attempt_id": attempt.id,
                "assessment_id": attempt.assessment_id,
                "student_id": attempt.user_id,
                "teacher_agent_id": attempt.agent_id,
                "score": attempt.score,
                "max_score": attempt.max_score,
                "percentage": attempt.percentage,
                "passed": attempt.passed,
            },
        )
        db.commit()
        return {
            "attempt_id": attempt.id,
            "percentage": attempt.percentage,
            "passed": attempt.passed,
            "reported_to": MainManagerService.SLUG,
        }

    @staticmethod
    def receive_payment_confirmation(db: Session, transaction_id: str) -> dict:
        transaction = db.get(PaymentTransaction, transaction_id)
        if transaction is None:
            raise ValueError("Payment transaction not found.")
        if transaction.status != PaymentStatus.CONFIRMED:
            raise ValueError("Payment is not confirmed; manager cannot activate access.")
        MainManagerService.record_event(
            db,
            event_name="payments.confirmed",
            actor_user_id=transaction.user_id,
            payload={
                "transaction_id": transaction.id,
                "user_id": transaction.user_id,
                "product_key": transaction.product_key,
                "amount": transaction.amount,
                "currency": transaction.currency,
            },
        )
        db.commit()
        return {"transaction_id": transaction.id, "access_authority": "tofan-main"}

    @staticmethod
    def student_snapshot(db: Session, user_id: str) -> dict:
        user = db.get(User, user_id)
        if user is None:
            raise ValueError("Student not found.")
        steps = db.scalars(select(TeachingStep).where(
            TeachingStep.user_id == user_id,
            TeachingStep.source == TeachingSource.GLOBAL_CURRICULUM,
        )).all()
        attempts = db.scalars(select(CurriculumAssessmentAttempt).where(
            CurriculumAssessmentAttempt.user_id == user_id,
        )).all()
        return {
            "student_id": user_id,
            "display_name": user.display_name,
            "global_steps_completed": sum(s.status == TeachingStepStatus.COMPLETED for s in steps),
            "global_steps_total_records": len(steps),
            "assessments": [
                {
                    "attempt_id": a.id,
                    "assessment_id": a.assessment_id,
                    "percentage": a.percentage,
                    "passed": a.passed,
                    "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                }
                for a in attempts
            ],
        }
