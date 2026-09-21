"""Central authority service for TOFAN's main manager agent.

The main manager is the system authority for payments, assessment reports,
student progress, and teacher-agent oversight. It never trusts client claims.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.agents.models import Agent, AgentKind, AgentRole, AgentStatus, AgentRun
from app.db.assessment_models import CurriculumAssessmentAttempt
from app.db.identity_models import PaymentTransaction, PaymentStatus, StudentProfile, UserType
from app.db.models import AuditLog, TeachingStep, TeachingStepStatus, TeachingSource, User
from app.agents.teacher import create_curriculum_teacher_agent
from app.notifications.service import create_notification


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
        if actor_user_id:
            create_notification(
                db,
                user_id=actor_user_id,
                event_type=event_name,
                title="تحديث من TOFAN Main Manager",
                message=f"تم تسجيل الحدث: {event_name} — القرار: {decision}.",
                resource_type=resource_type,
                resource_id=resource_id,
            )
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
    def process_event(db: Session, event_name: str, actor_user_id: str | None, payload: dict) -> dict:
        """Evaluate a trusted system event and persist the manager's decision."""
        if event_name == "education.curriculum_assessment_result":
            passed = bool(payload.get("passed"))
            decision = "course_passed" if passed else "course_not_passed"
            action = "education.course_completion.recorded" if passed else "education.assessment.retry_required"
        elif event_name == "education.exam_result":
            passed = bool(payload.get("passed"))
            decision = "file_exam_passed" if passed else "file_exam_not_passed"
            action = "education.file_exam.recorded" if passed else "education.file_exam.retry_required"
        elif event_name == "payments.confirmed":
            decision = "global_access_authorized"
            action = "manager.payment_access.activated"
        elif event_name == "manager.teacher_provision.requested":
            decision = "teacher_provision_requested"
            action = "manager.teacher_provision.evaluate"
        else:
            decision = "event_recorded_no_automatic_action"
            action = "manager.event.recorded"

        MainManagerService.record_event(
            db,
            event_name=event_name,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=payload.get("resource_type"),
            resource_id=payload.get("resource_id"),
            decision=decision,
            payload=payload,
        )
        db.commit()
        return {"event": event_name, "decision": decision, "action": action}

    @staticmethod
    def student_snapshot(db: Session, user_id: str) -> dict:
        """Return a complete manager-facing student operational snapshot."""
        from app.db.curriculum_models import CourseAssessment, CurriculumCourse
        from app.db.models import AuditLog, Entitlement, TeachingAssessment, TeachingUsage
        from app.db.progress_models import LearningProgress, LearningWeakPoint, LearningNextStep

        user = db.get(User, user_id)
        if user is None:
            raise ValueError("Student not found.")

        profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))
        if profile is None:
            raise ValueError("Student profile not found.")

        steps = db.scalars(
            select(TeachingStep)
            .where(TeachingStep.user_id == user_id)
            .order_by(TeachingStep.position)
        ).all()
        attempts = db.scalars(
            select(CurriculumAssessmentAttempt)
            .where(CurriculumAssessmentAttempt.user_id == user_id)
            .order_by(desc(CurriculumAssessmentAttempt.started_at))
        ).all()
        payments = db.scalars(
            select(PaymentTransaction)
            .where(PaymentTransaction.user_id == user_id)
            .order_by(desc(PaymentTransaction.created_at))
        ).all()
        file_exams = db.scalars(
            select(TeachingAssessment)
            .where(TeachingAssessment.user_id == user_id)
            .order_by(desc(TeachingAssessment.created_at))
        ).all()
        activity = db.scalars(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.created_at))
            .limit(20)
        ).all()
        usages = db.scalars(
            select(TeachingUsage)
            .where(TeachingUsage.user_id == user_id)
            .order_by(TeachingUsage.source)
        ).all()
        entitlements = db.scalars(
            select(Entitlement)
            .where(Entitlement.user_id == user_id)
            .order_by(desc(Entitlement.granted_at))
        ).all()
        step_teacher_ids = {s.agent_id for s in steps if s.agent_id}
        teachers = db.scalars(
            select(Agent)
            .where(
                Agent.id.in_(step_teacher_ids),
                Agent.kind == AgentKind.TEACHER,
            )
            .order_by(Agent.name)
        ).all() if step_teacher_ids else []

        course_ids = set()
        for step in steps:
            scope_key = step.scope_key or ""
            marker = "course:"
            if marker in scope_key:
                course_id = scope_key.split(marker, 1)[1].split(":unit:", 1)[0]
                if course_id:
                    course_ids.add(course_id)
        course_ids.update(t.curriculum_course_id for t in teachers if t.curriculum_course_id)
        assessment_ids = {a.assessment_id for a in attempts if a.assessment_id}
        if assessment_ids:
            assessment_course_ids = db.scalars(
                select(CourseAssessment.course_id).where(CourseAssessment.id.in_(assessment_ids))
            ).all()
            course_ids.update(assessment_course_ids)

        courses = db.scalars(
            select(CurriculumCourse).where(CurriculumCourse.id.in_(course_ids))
        ).all() if course_ids else []
        course_map = {c.id: c for c in courses}

        progress = []
        for step in steps:
            scope_key = step.scope_key or ""
            course_id = scope_key.split("course:", 1)[1].split(":unit:", 1)[0] if "course:" in scope_key else None
            course = course_map.get(course_id)
            progress.append({
                "step_id": step.id,
                "source": step.source,
                "scope_key": step.scope_key,
                "position": step.position,
                "status": step.status,
                "attempts": step.attempts,
                "understanding_verified": step.understanding_verified,
                "student_confirmed": step.student_confirmed,
                "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                "course_id": course.id if course else None,
                "course_code": course.code if course else None,
                "course_name": course.name if course else None,
            })

        persistent_progress = db.scalars(
            select(LearningProgress).where(LearningProgress.user_id == user_id)
        ).all()
        weak_points = db.scalars(
            select(LearningWeakPoint).where(
                LearningWeakPoint.user_id == user_id,
                LearningWeakPoint.resolved.is_(False),
            ).order_by(desc(LearningWeakPoint.occurrences))
        ).all()
        next_steps = db.scalars(
            select(LearningNextStep).where(LearningNextStep.user_id == user_id)
        ).all()

        return {
            "student": {
                "student_id": user_id,
                "profile_id": profile.id,
                "display_name": user.display_name,
                "full_name": profile.full_name,
                "email": user.email,
                "phone": user.phone,
                "is_active": user.is_active,
                "user_type": profile.user_type,
                "age": profile.age,
                "institution_id": profile.institution_id,
                "college_unit_id": profile.college_unit_id,
                "major_unit_id": profile.major_unit_id,
                "profile_status": profile.profile_status,
                "biometric_verified": profile.biometric_verified,
                "verified_at": profile.verified_at.isoformat() if profile.verified_at else None,
                "created_at": profile.created_at.isoformat(),
                "updated_at": profile.updated_at.isoformat(),
            },
            "teaching_usage": [
                {
                    "agent_id": u.agent_id,
                    "source": u.source,
                    "files_used": u.files_used,
                    "files_limit": u.files_limit,
                    "response_chars_used": u.response_chars_used,
                    "response_chars_limit": u.response_chars_limit,
                    "response_chars_remaining": max(0, u.response_chars_limit - u.response_chars_used),
                    "paid_access": u.paid_access,
                    "quota_started_at": u.quota_started_at.isoformat() if u.quota_started_at else None,
                }
                for u in usages
            ],
            "progress": {
                "steps_total": len(steps),
                "steps_completed": sum(s.status == TeachingStepStatus.COMPLETED for s in steps),
                "steps_active": sum(s.status == TeachingStepStatus.ACTIVE for s in steps),
                "steps": progress,
            },
            "learning_progress": {
                "lessons": [
                    {
                        "course_id": p.course_id,
                        "lesson_id": p.lesson_id,
                        "status": p.status,
                        "attempts": p.attempts,
                        "understanding_verified": p.understanding_verified,
                        "assessment_percentage": p.assessment_percentage,
                        "last_score": p.last_score,
                        "completed_at": p.completed_at.isoformat() if p.completed_at else None,
                    }
                    for p in persistent_progress
                ],
                "weak_points": [
                    {
                        "course_id": w.course_id,
                        "lesson_id": w.lesson_id,
                        "topic": w.topic,
                        "reason": w.reason,
                        "severity": w.severity,
                        "occurrences": w.occurrences,
                    }
                    for w in weak_points
                ],
                "next_steps": [
                    {
                        "course_id": n.course_id,
                        "lesson_id": n.lesson_id,
                        "action": n.action,
                        "reason": n.reason,
                        "priority": n.priority,
                    }
                    for n in next_steps
                ],
            },
            "teacher_agents": [
                {
                    "agent_id": t.id,
                    "name": t.name,
                    "slug": t.slug,
                    "status": t.status,
                    "curriculum_course_id": t.curriculum_course_id,
                    "course_code": course_map.get(t.curriculum_course_id).code if t.curriculum_course_id in course_map else None,
                    "course_name": course_map.get(t.curriculum_course_id).name if t.curriculum_course_id in course_map else None,
                }
                for t in teachers if t.curriculum_course_id in course_map
            ],
            "file_exams": [
                {
                    "assessment_id": e.id,
                    "content_file_id": e.content_file_id,
                    "score": e.score,
                    "max_score": e.max_score,
                    "percentage": e.percentage,
                    "passed": e.passed,
                    "created_at": e.created_at.isoformat(),
                }
                for e in file_exams
            ],
            "activity": [
                {
                    "id": a.id,
                    "action": a.action,
                    "resource_type": a.resource_type,
                    "resource_id": a.resource_id,
                    "created_at": a.created_at.isoformat(),
                    "details": a.details,
                }
                for a in activity
            ],
            "assessments": [
                {
                    "attempt_id": a.id,
                    "assessment_id": a.assessment_id,
                    "percentage": a.percentage,
                    "score": a.score,
                    "max_score": a.max_score,
                    "status": a.status,
                    "passed": a.passed,
                    "started_at": a.started_at.isoformat(),
                    "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                    "graded_at": a.graded_at.isoformat() if a.graded_at else None,
                }
                for a in attempts
            ],
            "payments": [
                {
                    "transaction_id": p.id,
                    "product_key": p.product_key,
                    "status": p.status,
                    "amount": p.amount,
                    "currency": p.currency,
                    "reference": p.reference,
                    "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
                    "created_at": p.created_at.isoformat(),
                }
                for p in payments
            ],
            "entitlements": [
                {
                    "id": e.id,
                    "access_type": e.access_type,
                    "content_file_id": e.content_file_id,
                    "lecture_id": e.lecture_id,
                    "granted_at": e.granted_at.isoformat(),
                    "expires_at": e.expires_at.isoformat() if e.expires_at else None,
                }
                for e in entitlements
            ],
            "global_steps_completed": sum(
                s.status == TeachingStepStatus.COMPLETED and s.source == TeachingSource.GLOBAL_CURRICULUM
                for s in steps
            ),
            "global_steps_total_records": sum(
                s.source == TeachingSource.GLOBAL_CURRICULUM for s in steps
            ),
        }

    @staticmethod
    def dashboard_summary(db: Session) -> dict:
        """Return the manager's operational dashboard summary."""
        from app.db.curriculum_models import CurriculumCourse, CurriculumLesson, Curriculum
        total_users = db.scalar(select(func.count(User.id))) or 0
        total_profiles = db.scalar(select(func.count(StudentProfile.id))) or 0
        university_students = db.scalar(select(func.count(StudentProfile.id)).where(StudentProfile.user_type == UserType.UNIVERSITY_STUDENT)) or 0
        independent_learners = db.scalar(select(func.count(StudentProfile.id)).where(StudentProfile.user_type == UserType.INDEPENDENT_LEARNER)) or 0
        active_teachers = db.scalar(select(func.count(Agent.id)).where(Agent.kind == AgentKind.TEACHER, Agent.status == AgentStatus.ACTIVE)) or 0
        total_teachers = db.scalar(select(func.count(Agent.id)).where(Agent.kind == AgentKind.TEACHER)) or 0
        active_curricula = db.scalar(select(func.count(Curriculum.id)).where(Curriculum.status == "active")) or 0
        total_courses = db.scalar(select(func.count(CurriculumCourse.id)).where(CurriculumCourse.is_active.is_(True))) or 0
        total_lessons = db.scalar(select(func.count(CurriculumLesson.id))) or 0
        total_assessments = db.scalar(select(func.count(CurriculumAssessmentAttempt.id))) or 0
        passed_assessments = db.scalar(select(func.count(CurriculumAssessmentAttempt.id)).where(CurriculumAssessmentAttempt.passed.is_(True))) or 0
        failed_assessments = db.scalar(select(func.count(CurriculumAssessmentAttempt.id)).where(CurriculumAssessmentAttempt.passed.is_(False))) or 0
        pending_payments = db.scalar(select(func.count(PaymentTransaction.id)).where(PaymentTransaction.status == PaymentStatus.PENDING)) or 0
        confirmed_payments = db.scalar(select(func.count(PaymentTransaction.id)).where(PaymentTransaction.status == PaymentStatus.CONFIRMED)) or 0
        audit_events = db.scalar(select(func.count(AuditLog.id))) or 0
        return {
            "users": {"total": total_users, "profiles": total_profiles, "university_students": university_students, "independent_learners": independent_learners},
            "teachers": {"total": total_teachers, "active": active_teachers},
            "curriculum": {"active_curricula": active_curricula, "active_courses": total_courses, "lessons": total_lessons},
            "assessments": {"attempts": total_assessments, "passed": passed_assessments, "failed": failed_assessments},
            "payments": {"pending": pending_payments, "confirmed": confirmed_payments},
            "audit": {"events": audit_events},
        }

    @staticmethod
    def students(db: Session, limit: int = 50, offset: int = 0, query: str | None = None) -> dict:
        stmt = select(StudentProfile)
        count_stmt = select(func.count(StudentProfile.id))
        if query:
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(User, User.id == StudentProfile.user_id).where(
                StudentProfile.full_name.ilike(pattern) | User.display_name.ilike(pattern) |
                User.email.ilike(pattern) | User.phone.ilike(pattern)
            )
            count_stmt = count_stmt.join(User, User.id == StudentProfile.user_id).where(
                StudentProfile.full_name.ilike(pattern) | User.display_name.ilike(pattern) |
                User.email.ilike(pattern) | User.phone.ilike(pattern)
            )
        total = db.scalar(count_stmt) or 0
        rows = db.scalars(stmt.order_by(desc(StudentProfile.updated_at)).offset(offset).limit(limit)).all()
        return {"total": total, "limit": limit, "offset": offset, "query": query or "", "students": [{
            "profile_id": p.id, "user_id": p.user_id, "name": p.full_name, "user_type": p.user_type,
            "profile_status": p.profile_status, "biometric_verified": p.biometric_verified,
            "created_at": p.created_at.isoformat(), "updated_at": p.updated_at.isoformat()
        } for p in rows]}

    @staticmethod
    def assessments(db: Session, limit: int = 50, offset: int = 0) -> dict:
        total = db.scalar(select(func.count(CurriculumAssessmentAttempt.id))) or 0
        rows = db.scalars(select(CurriculumAssessmentAttempt).order_by(desc(CurriculumAssessmentAttempt.submitted_at), desc(CurriculumAssessmentAttempt.started_at)).offset(offset).limit(limit)).all()
        return {"total": total, "limit": limit, "offset": offset, "assessments": [{
            "attempt_id": a.id, "user_id": a.user_id, "agent_id": a.agent_id, "assessment_id": a.assessment_id,
            "status": a.status, "score": a.score, "max_score": a.max_score, "percentage": a.percentage, "passed": a.passed,
            "started_at": a.started_at.isoformat(), "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            "graded_at": a.graded_at.isoformat() if a.graded_at else None
        } for a in rows]}

    @staticmethod
    def payments(db: Session, limit: int = 50, offset: int = 0) -> dict:
        total = db.scalar(select(func.count(PaymentTransaction.id))) or 0
        rows = db.scalars(select(PaymentTransaction).order_by(desc(PaymentTransaction.created_at)).offset(offset).limit(limit)).all()
        return {"total": total, "limit": limit, "offset": offset, "payments": [{
            "transaction_id": p.id, "user_id": p.user_id, "product_key": p.product_key, "status": p.status,
            "amount": p.amount, "currency": p.currency, "reference": p.reference, "confirmed_by_agent_id": p.confirmed_by_agent_id,
            "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None, "created_at": p.created_at.isoformat()
        } for p in rows]}

    @staticmethod
    def audit_log(db: Session, limit: int = 50, offset: int = 0) -> dict:
        total = db.scalar(select(func.count(AuditLog.id))) or 0
        rows = db.scalars(select(AuditLog).order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)).all()
        return {"total": total, "limit": limit, "offset": offset, "events": [{
            "id": a.id, "user_id": a.user_id, "action": a.action, "resource_type": a.resource_type,
            "resource_id": a.resource_id, "created_at": a.created_at.isoformat(), "details": a.details
        } for a in rows]}
    @staticmethod
    def provision_specialist(db: Session, role: AgentRole, *, name: str | None = None, description: str | None = None) -> dict:
        if role in {AgentRole.GENERAL_MANAGER, AgentRole.TEACHER}:
            raise ValueError("Use the dedicated manager or teacher provisioning workflow for this role.")
        slug = f"specialist-tofan-{role.value}"
        existing = db.scalar(select(Agent).where(Agent.slug == slug))
        if existing is not None:
            return {"agent_id": existing.id, "slug": existing.slug, "role": existing.role, "status": existing.status, "created": False}
        agent = Agent(
            name=name or f"وكيل {role.value}",
            slug=slug,
            kind=AgentKind.SPECIALIST,
            role=role,
            status=AgentStatus.ACTIVE,
            description=description or f"وكيل ذكاء اصطناعي متخصص في {role.value} لأكاديمية طوفان الذكية.",
            system_prompt=(
                f"You are TOFAN's {role.value} specialist AI agent. "
                "Operate only within your assigned domain, use approved tools, "
                "protect student data, and escalate cross-domain or sensitive decisions to tofan-main."
            ),
            memory_enabled=True,
        )
        db.add(agent)
        db.flush()
        for tool_name in ("academy.search", "academy.structure"):
            db.add(AgentTool(agent_id=agent.id, tool_name=tool_name, enabled=True))
        MainManagerService.record_event(
            db, event_name="manager.specialist_provision.completed", actor_user_id=None,
            action="manager.specialist_provision.created", resource_type="agent", resource_id=agent.id,
            decision="specialist_created", payload={"role": role.value, "slug": slug},
        )
        db.commit()
        db.refresh(agent)
        return {"agent_id": agent.id, "slug": agent.slug, "role": agent.role, "status": agent.status, "created": True}

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
    def courses(db: Session) -> dict:
        from app.db.curriculum_models import CurriculumCourse, Curriculum

        rows = db.scalars(
            select(CurriculumCourse)
            .join(Curriculum, Curriculum.id == CurriculumCourse.curriculum_id)
            .where(CurriculumCourse.is_active.is_(True))
            .order_by(CurriculumCourse.position, CurriculumCourse.name)
        ).all()
        return {
            "courses": [
                {
                    "course_id": c.id,
                    "code": c.code,
                    "name": c.name,
                    "stage_id": c.stage_id,
                    "curriculum_id": c.curriculum_id,
                    "course_type": c.course_type,
                }
                for c in rows
            ]
        }

    @staticmethod
    def teacher_overview(db: Session) -> list[dict]:
        teachers = db.scalars(select(Agent).where(Agent.kind == AgentKind.TEACHER).order_by(Agent.name)).all()
        return [{"agent_id": t.id, "slug": t.slug, "name": t.name, "status": t.status,
                 "curriculum_course_id": t.curriculum_course_id} for t in teachers]
