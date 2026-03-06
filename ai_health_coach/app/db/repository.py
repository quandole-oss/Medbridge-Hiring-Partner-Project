import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Goal, Patient


async def get_patient(session: AsyncSession, patient_id: str) -> Optional[Patient]:
    result = await session.execute(
        select(Patient).where(Patient.patient_id == patient_id)
    )
    return result.scalar_one_or_none()


async def create_patient(session: AsyncSession, patient_id: str) -> Patient:
    patient = Patient(patient_id=patient_id)
    session.add(patient)
    await session.commit()
    await session.refresh(patient)
    return patient


async def update_patient_phase(
    session: AsyncSession, patient_id: str, phase: str
) -> None:
    patient = await get_patient(session, patient_id)
    if patient:
        patient.current_phase = phase
        await session.commit()


async def update_patient_last_message(
    session: AsyncSession, patient_id: str
) -> None:
    patient = await get_patient(session, patient_id)
    if patient:
        patient.last_message_at = datetime.datetime.now(datetime.timezone.utc)
        await session.commit()


async def grant_consent(session: AsyncSession, patient_id: str) -> Patient:
    patient = await get_patient(session, patient_id)
    if not patient:
        patient = await create_patient(session, patient_id)
    patient.consent_status = True
    patient.enrollment_date = datetime.datetime.now(datetime.timezone.utc)
    patient.current_phase = "onboarding"
    await session.commit()
    await session.refresh(patient)
    return patient


async def create_goal(
    session: AsyncSession, patient_id: str, goal_text: str
) -> Goal:
    goal = Goal(patient_id=patient_id, goal_text=goal_text)
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    return goal


async def get_active_goal(session: AsyncSession, patient_id: str) -> Optional[Goal]:
    result = await session.execute(
        select(Goal)
        .where(Goal.patient_id == patient_id, Goal.is_active == True)
        .order_by(Goal.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def log_audit_event(
    session: AsyncSession,
    patient_id: str,
    event_type: str,
    payload: Optional[dict] = None,
) -> AuditLog:
    log = AuditLog(patient_id=patient_id, event_type=event_type, payload=payload)
    session.add(log)
    await session.commit()
    return log


async def get_disengaged_patients(
    session: AsyncSession, threshold_hours: int
) -> List[Patient]:
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        hours=threshold_hours
    )
    result = await session.execute(
        select(Patient).where(
            Patient.current_phase == "active",
            Patient.last_message_at < cutoff,
            Patient.unanswered_count < 3,
        )
    )
    return list(result.scalars().all())
