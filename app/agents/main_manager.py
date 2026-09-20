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
from app.db.models import AuditLog, TeachingStep, TeachingStepStatus, TeachingSource, User
from app.agents.teacher import create_curriculum_teacher_agent


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
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        decision: str = "accepted",
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
        db.add(AuditLog(
            user_id=actor_user_id,
            action=action or event_name,
            resource_type=resource_type,
            resource_id=resource_id,
            details=json.dumps({
                "manager_agent_id": manager.id,
                "manager_agent_slug": manager.slug,
                "event": event_name,
                "decision": decision,
                "payload": payload,
            }, ensure_ascii=False),
        ))
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
            action="manager.assessment_result.processed",
            resource_type="curriculum_assessment_attempt",
            resource_id=attempt.id,
            decision="course_passed" if attempt.passed else "course_not_passed",
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
            action="manager.payment_access.activated",
            resource_type="payment_transaction",
            resource_id=transaction.id,
            decision="global_access_authorized",
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


    @staticmethod
    def provision_teacher(db: Session, curriculum_course_id: str) -> dict:
        from app.db.curriculum_models import CurriculumCourse
        course = db.get(CurriculumCourse, curriculum_course_id)
        if course is None or not course.is_active:
            raise ValueError("Active TOFAN curriculum course not found.")
        slug = f"teacher-tofan-{course.code.lower()}"
        existing = db.scalar(select(Agent).where(Agent.slug == slug))
        if existing is not None:
            MainManagerService.record_event(
                db, event_name="manager.teacher_provision.requested", actor_user_id=None,
                action="manager.teacher_provision.reused", resource_type="agent", resource_id=existing.id,
                decision="existing_teacher_reused", payload={"curriculum_course_id": curriculum_course_id},
            )
            db.commit()
            return {"agent_id": existing.id, "slug": existing.slug, "status": existing.status, "created": False}
        agent = create_curriculum_teacher_agent(
            db, name=f"مدرس {course.name}", slug=slug,
            curriculum_course_id=course.id,
            description=f"وكيل مدرس لمقرر TOFAN {course.code}: {course.name}.",
        )
        MainManagerService.record_event(
            db, event_name="manager.teacher_provision.completed", actor_user_id=None,
            action="manager.teacher_provision.created", resource_type="agent", resource_id=agent.id,
            decision="teacher_created", payload={"curriculum_course_id": curriculum_course_id, "slug": agent.slug},
        )
        db.commit()
        return {"agent_id": agent.id, "slug": agent.slug, "status": agent.status, "created": True}

    @staticmethod
    def set_teacher_status(db: Session, agent_id: str, status: AgentStatus) -> dict:
        agent = db.get(Agent, agent_id)
        if agent is None or agent.kind != AgentKind.TEACHER:
            raise ValueError("Teacher agent not found.")
        if agent.status == AgentStatus.ARCHIVED:
            raise ValueError("Archived teacher agents cannot be reactivated.")
        previous_status = agent.status
        agent.status = status
        MainManagerService.record_event(
            db, event_name="manager.teacher_status.changed", actor_user_id=None,
            action="manager.teacher_status.updated", resource_type="agent", resource_id=agent.id,
            decision="status_changed", payload={"previous_status": previous_status, "new_status": status},
        )
        db.commit()
        return {"agent_id": agent.id, "slug": agent.slug, "status": agent.status}

    @staticmethod
    def teacher_overview(db: Session) -> list[dict]:
        teachers = db.scalars(select(Agent).where(Agent.kind == AgentKind.TEACHER).order_by(Agent.name)).all()
        return [{"agent_id": t.id, "slug": t.slug, "name": t.name, "status": t.status,
                 "curriculum_course_id": t.curriculum_course_id} for t in teachers]
