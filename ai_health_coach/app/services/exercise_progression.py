"""Exercise progression service — extracted adjustment pipeline + auto-progression."""
import datetime
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Exercise as ExerciseModel
from app.db.repository import (
    find_replacement_target,
    get_exercise_by_id,
    get_exercise_completions,
    get_patient,
    log_audit_event,
    replace_exercise,
)
from app.services.llm import get_exercise_adjustment

logger = logging.getLogger(__name__)


async def perform_exercise_adjustment(
    session: AsyncSession,
    patient_id: str,
    exercise_id: int,
    difficulty: str,
    feedback: Optional[str] = None,
    source: str = "manual",
) -> Optional[dict]:
    """Core exercise adjustment pipeline — reusable by API endpoint and auto-progression.

    Returns dict with original_exercise, new_exercise, reasoning, target_day, target_exercise_name
    or None if exercise not found.
    """
    patient = await get_patient(session, patient_id)
    if not patient:
        return None

    exercise = await get_exercise_by_id(session, exercise_id)
    if not exercise or exercise.patient_id != patient_id:
        return None

    # Calculate current day from enrollment date
    current_day = exercise.day_number
    if patient.enrollment_date:
        now = datetime.datetime.now(datetime.timezone.utc)
        enrollment = patient.enrollment_date
        if enrollment.tzinfo is None:
            enrollment = enrollment.replace(tzinfo=datetime.timezone.utc)
        current_day = min(max((now - enrollment).days + 1, 1), 7)

    # Fetch completion data for set_statuses context
    today = datetime.date.today()
    completions = await get_exercise_completions(session, patient_id, today)
    comp_map = {c.exercise_id: c for c in completions}
    source_comp = comp_map.get(exercise_id)
    source_set_statuses = source_comp.set_statuses if source_comp else None

    adjustment = await get_exercise_adjustment(
        exercise=exercise,
        difficulty=difficulty,
        feedback=feedback,
        set_statuses=source_set_statuses,
    )

    # Find replacement target on a different day
    target = await find_replacement_target(session, patient_id, exercise, current_day)

    if target:
        target_exercise_id = target.exercise_id
        target_day = target.day_number
        target_exercise_name = target.name
    else:
        target_day = (current_day % 7) + 1
        target_exercise_id = None
        target_exercise_name = None

    if target_exercise_id:
        new_exercise = await replace_exercise(
            session,
            patient_id=patient_id,
            old_exercise_id=target_exercise_id,
            name=adjustment["name"],
            description=adjustment["description"],
            body_part=adjustment["body_part"],
            sets=adjustment["sets"],
            reps=adjustment["reps"],
            hold_seconds=adjustment.get("hold_seconds"),
        )
    else:
        new_exercise = ExerciseModel(
            patient_id=patient_id,
            name=adjustment["name"],
            description=adjustment["description"],
            body_part=adjustment["body_part"],
            sets=adjustment["sets"],
            reps=adjustment["reps"],
            hold_seconds=adjustment.get("hold_seconds"),
            day_number=target_day,
            sort_order=99,
            is_active=True,
        )
        session.add(new_exercise)
        await session.commit()
        await session.refresh(new_exercise)

    day_label = "Day {}".format(target_day)
    if target_day <= current_day:
        day_label += " (next cycle)"

    replaced_name = target_exercise_name or "new slot on {}".format(day_label)
    reasoning = "{}: {} -> {}. {}".format(
        day_label, replaced_name, new_exercise.name, adjustment["reasoning"]
    )

    await log_audit_event(
        session,
        patient_id,
        "exercise_adjusted" if source == "manual" else "auto_exercise_adjustment",
        {
            "source": source,
            "source_exercise_id": exercise_id,
            "target_exercise_id": target.exercise_id if target else None,
            "new_exercise_id": new_exercise.exercise_id,
            "target_day": target_day,
            "difficulty": difficulty,
            "reasoning": adjustment["reasoning"],
        },
    )

    return {
        "exercise": exercise,
        "new_exercise": new_exercise,
        "reasoning": reasoning,
        "target_day": target_day,
        "target_exercise_name": target_exercise_name,
        "source_comp": source_comp,
        "source_set_statuses": source_set_statuses,
    }


async def check_and_auto_adjust(
    session: AsyncSession,
    patient_id: str,
    exercise_id: int,
    difficulty: str,
) -> Optional[dict]:
    """Check if auto-adjustment threshold is met and trigger adjustment if so.

    Threshold: 2+ completions with same difficulty signal in last 3 days
    for the same exercise.
    """
    if difficulty not in ("too_easy", "too_hard"):
        return None

    from app.db.repository import get_recent_difficulty_signals

    signals = await get_recent_difficulty_signals(
        session, patient_id, exercise_id, days=3, signal=difficulty
    )

    if len(signals) < 2:
        return None

    logger.info(
        "Auto-adjusting exercise %d for patient %s: %d %s signals in 3 days",
        exercise_id, patient_id, len(signals), difficulty,
    )

    return await perform_exercise_adjustment(
        session, patient_id, exercise_id, difficulty, source="auto"
    )
