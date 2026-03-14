from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Pathway, PathwayWeek, Patient
from app.db.repository import get_adherence_stats, get_outcome_summary


async def evaluate_advancement(session: AsyncSession, patient_id: str) -> dict:
    """Check whether a patient qualifies to advance to the next pathway week.

    Returns {advanced: bool, new_week: int, reason: str}.
    Idempotent: calling twice at the same state returns the same result.
    """
    patient_result = await session.execute(
        select(Patient).where(Patient.patient_id == patient_id)
    )
    patient = patient_result.scalar_one_or_none()
    if not patient or not patient.pathway_id:
        return {"advanced": False, "new_week": 1, "reason": "no_pathway"}

    # Get pathway info
    pathway_result = await session.execute(
        select(Pathway).where(Pathway.pathway_id == patient.pathway_id)
    )
    pathway = pathway_result.scalar_one_or_none()
    if not pathway:
        return {"advanced": False, "new_week": patient.current_week, "reason": "pathway_not_found"}

    # Already at final week
    if patient.current_week >= pathway.total_weeks:
        return {"advanced": False, "new_week": patient.current_week, "reason": "already_final_week"}

    # Get current week's thresholds
    week_result = await session.execute(
        select(PathwayWeek).where(
            PathwayWeek.pathway_id == patient.pathway_id,
            PathwayWeek.week_number == patient.current_week,
        )
    )
    current_pw = week_result.scalar_one_or_none()
    if not current_pw:
        return {"advanced": False, "new_week": patient.current_week, "reason": "week_config_missing"}

    # Check adherence for current week
    adherence = await get_adherence_stats(session, patient_id, week_number=patient.current_week)
    completion_rate = adherence["completion_rate"] / 100.0  # convert from percentage

    if completion_rate < current_pw.advancement_threshold:
        return {
            "advanced": False,
            "new_week": patient.current_week,
            "reason": "adherence",
            "completion_rate": round(completion_rate * 100, 1),
            "threshold": round(current_pw.advancement_threshold * 100, 1),
        }

    # Check pain ceiling
    if current_pw.pain_ceiling is not None:
        outcomes = await get_outcome_summary(session, patient_id)
        if outcomes["latest"]:
            latest_pain = outcomes["latest"]["pain_score"]
            if latest_pain > current_pw.pain_ceiling:
                return {
                    "advanced": False,
                    "new_week": patient.current_week,
                    "reason": "pain",
                    "latest_pain": latest_pain,
                    "pain_ceiling": current_pw.pain_ceiling,
                }

    # Advance!
    new_week = patient.current_week + 1
    patient.current_week = new_week
    await session.commit()

    return {
        "advanced": True,
        "new_week": new_week,
        "reason": "advanced",
    }
