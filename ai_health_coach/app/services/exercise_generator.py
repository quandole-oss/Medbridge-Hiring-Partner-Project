import datetime
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Exercise
from app.db.repository import (
    bulk_create_exercises,
    deactivate_exercises_for_goal,
    get_active_goals,
    get_daily_exercise_counts,
    get_patient_exercises,
)
from app.services.llm import generate_exercises_for_goal, rebalance_exercises

logger = logging.getLogger(__name__)

MAX_EXERCISES_PER_DAY = 5
MIN_EXERCISES_PER_GOAL = 2
MAX_EXERCISES_PER_GOAL = 5


async def generate_and_persist_exercises(
    session: AsyncSession,
    patient_id: str,
    goal_id: int,
    goal_text: str,
    target_date: Optional[datetime.date] = None,
) -> List[Exercise]:
    """Generate AI exercises for a goal and persist them."""
    # 1. Fetch current state
    all_exercises = await get_patient_exercises(session, patient_id)
    daily_counts = await get_daily_exercise_counts(session, patient_id)

    # 2. Summarize existing exercises for the LLM
    existing_summary = "\n".join(
        f"- {e.name} (Day {e.day_number}, {e.body_part})"
        for e in all_exercises
    ) or "No existing exercises"

    # 3. Call LLM to generate exercises
    target_str = target_date.isoformat() if target_date else None
    result = await generate_exercises_for_goal(
        goal_text=goal_text,
        target_date=target_str,
        existing_exercises_summary=existing_summary,
        daily_counts=daily_counts,
        max_per_day=MAX_EXERCISES_PER_DAY,
    )

    if not result.exercises:
        logger.warning("No exercises generated for goal %d", goal_id)
        return []

    # 4. Clamp to MAX_EXERCISES_PER_GOAL
    exercises_to_create = result.exercises[:MAX_EXERCISES_PER_GOAL]

    # 5. Validate and clamp day assignments
    for ex in exercises_to_create:
        day_count = daily_counts.get(ex.day_number, 0)
        if day_count >= MAX_EXERCISES_PER_DAY:
            # Find a day with room
            for d in range(1, 8):
                if daily_counts.get(d, 0) < MAX_EXERCISES_PER_DAY:
                    ex.day_number = d
                    break

    # 6. Build exercise data dicts
    exercises_data = []
    for i, ex in enumerate(exercises_to_create):
        exercises_data.append({
            "name": ex.name,
            "description": ex.description,
            "setup_instructions": ex.setup_instructions,
            "execution_steps": ex.execution_steps,
            "form_cues": ex.form_cues,
            "common_mistakes": ex.common_mistakes,
            "body_part": ex.body_part,
            "sets": ex.sets,
            "reps": ex.reps,
            "hold_seconds": ex.hold_seconds,
            "day_number": ex.day_number,
            "sort_order": 10 + i,
            "goal_id": goal_id,
            "is_active": True,
        })
        # Update counts for subsequent exercises
        daily_counts[ex.day_number] = daily_counts.get(ex.day_number, 0) + 1

    # 7. Persist
    new_exercises = await bulk_create_exercises(session, patient_id, exercises_data)
    logger.info(
        "Generated %d exercises for goal %d (patient %s)",
        len(new_exercises), goal_id, patient_id,
    )

    # 8. Check if rebalancing is needed
    updated_counts = await get_daily_exercise_counts(session, patient_id)
    over_cap = any(c > MAX_EXERCISES_PER_DAY for c in updated_counts.values())
    if over_cap:
        await _rebalance_if_needed(session, patient_id)

    return new_exercises


async def _rebalance_if_needed(session: AsyncSession, patient_id: str) -> None:
    """Rebalance exercises if any day exceeds the cap."""
    goals = await get_active_goals(session, patient_id)
    all_exercises = await get_patient_exercises(session, patient_id)

    goals_summary = "\n".join(
        f"- Goal {g.goal_id}: {g.goal_text}"
        + (f" (target: {g.target_date})" if g.target_date else "")
        for g in goals
    )

    exercises_by_day = {}
    for ex in all_exercises:
        day = ex.day_number
        if day not in exercises_by_day:
            exercises_by_day[day] = []
        exercises_by_day[day].append(
            f"  id={ex.exercise_id}, name={ex.name}, goal_id={ex.goal_id}"
        )

    day_str = "\n".join(
        f"Day {d}:\n" + "\n".join(exs)
        for d, exs in sorted(exercises_by_day.items())
    )

    result = await rebalance_exercises(goals_summary, day_str, MAX_EXERCISES_PER_DAY)

    if result.exercise_ids_to_deactivate:
        from sqlalchemy import select
        from app.db.models import Exercise as ExModel

        for eid in result.exercise_ids_to_deactivate:
            res = await session.execute(
                select(ExModel).where(ExModel.exercise_id == eid)
            )
            ex = res.scalar_one_or_none()
            if ex:
                ex.is_active = False
        await session.commit()
        logger.info(
            "Rebalanced: deactivated %d exercises for patient %s",
            len(result.exercise_ids_to_deactivate), patient_id,
        )


async def remove_exercises_for_goal(
    session: AsyncSession, patient_id: str, goal_id: int
) -> int:
    """Deactivate all exercises associated with a goal."""
    return await deactivate_exercises_for_goal(session, patient_id, goal_id)
