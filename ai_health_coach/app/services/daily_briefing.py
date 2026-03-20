"""Daily briefing service — generates and caches personalized daily coaching messages."""
import datetime
import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import (
    get_active_goals,
    get_adherence_stats,
    get_outcome_summary,
    get_patient,
    get_patient_exercises,
    get_patient_insights_db,
)
from app.graph.prompts import DAILY_BRIEFING_PROMPT
from app.services.llm import get_safety_llm

logger = logging.getLogger(__name__)


async def get_daily_briefing_cached(
    session: AsyncSession, patient_id: str, date: datetime.date
) -> Optional[str]:
    """Return cached briefing for today if it exists."""
    from app.db.repository import get_daily_briefing
    briefing = await get_daily_briefing(session, patient_id, date)
    return briefing.message if briefing else None


async def generate_daily_briefing(
    session: AsyncSession, patient_id: str
) -> dict:
    """Generate personalized daily coaching message. Returns cached if exists for today.

    Returns dict with keys: message, is_cached
    """
    today = datetime.date.today()

    # Check cache
    cached = await get_daily_briefing_cached(session, patient_id, today)
    if cached:
        return {"message": cached, "is_cached": True}

    patient = await get_patient(session, patient_id)
    if not patient:
        return {"message": "Welcome! Start your recovery journey today.", "is_cached": False}

    # Gather data
    adherence = await get_adherence_stats(session, patient_id)
    outcomes = await get_outcome_summary(session, patient_id)
    goals = await get_active_goals(session, patient_id)
    insights = await get_patient_insights_db(session, patient_id, limit=5)

    # Get today's exercises
    current_day = adherence.get("current_day", 1)
    today_exercises = await get_patient_exercises(session, patient_id, day=current_day)

    # Compute earned badges for context
    from app.db.repository import get_completed_goal_count
    from app.services.badges import compute_badges

    completed_goals = await get_completed_goal_count(session, patient_id)
    badges = compute_badges(adherence, len(goals), completed_goals)
    earned_badge_names = [b["name"] for b in badges if b["earned"]]

    # Build context
    goal_text = ", ".join(g.goal_text for g in goals) if goals else "No goals set"
    insight_text = "; ".join(i.content for i in insights) if insights else "New patient"
    exercise_names = ", ".join(e.name for e in today_exercises) if today_exercises else "Rest day"
    badge_text = ", ".join(earned_badge_names) if earned_badge_names else "None yet"

    context = (
        "Patient: {patient_id}\n"
        "Day {day} of program | Streak: {streak} days | Completion: {rate}%\n"
        "Goals: {goals}\n"
        "Today's exercises: {exercises} ({count} total)\n"
        "Pain trend: {pain} | Function trend: {function}\n"
        "Badges earned: {badges}\n"
        "What you know: {insights}"
    ).format(
        patient_id=patient_id,
        day=adherence.get("days_in_program", 1),
        streak=adherence.get("streak", 0),
        rate=adherence.get("completion_rate", 0),
        goals=goal_text,
        exercises=exercise_names,
        count=len(today_exercises),
        pain=outcomes.get("pain_trend", "stable"),
        function=outcomes.get("function_trend", "stable"),
        badges=badge_text,
        insights=insight_text,
    )

    # Generate with Haiku
    llm = get_safety_llm()
    try:
        response = await llm.ainvoke([
            SystemMessage(content=DAILY_BRIEFING_PROMPT),
            HumanMessage(content=context),
        ])
        message = response.content if isinstance(response.content, str) else str(response.content)
    except Exception:
        logger.exception("Daily briefing generation failed for %s", patient_id)
        message = "Good to see you today! You have {} exercises ready for you. Let's keep building on your progress!".format(
            len(today_exercises)
        )

    # Cache
    from app.db.repository import save_daily_briefing
    await save_daily_briefing(session, patient_id, today, message)

    return {"message": message, "is_cached": False}
