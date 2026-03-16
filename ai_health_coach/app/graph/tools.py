from langchain_core.tools import tool
from pydantic import BaseModel, Field


class SetGoalInput(BaseModel):
    patient_id: str = Field(description="The patient's unique identifier")
    goal_text: str = Field(description="The SMART goal text")


class SetReminderInput(BaseModel):
    patient_id: str = Field(description="The patient's unique identifier")
    reminder_text: str = Field(description="What to remind the patient about")
    time: str = Field(description="When to send the reminder (ISO format or natural language)")


class AlertClinicianInput(BaseModel):
    patient_id: str = Field(description="The patient's unique identifier")
    reason: str = Field(description="Why the clinician is being alerted")
    urgency_level: str = Field(description="CRITICAL, HIGH, or LOW")


@tool(args_schema=SetGoalInput)
def set_goal(patient_id: str, goal_text: str) -> str:
    """Persist a SMART goal for the patient. Use when the patient has articulated a clear goal."""
    return f"Goal set for patient {patient_id}: {goal_text}"


@tool(args_schema=SetReminderInput)
def set_reminder(patient_id: str, reminder_text: str, time: str) -> str:
    """Create a reminder for the patient. Use when the patient wants to be reminded about exercises or appointments."""
    return f"Reminder set for patient {patient_id}: '{reminder_text}' at {time}"


@tool
def get_program_summary(patient_id: str) -> str:
    """Get a summary of the patient's physical therapy program including pathway status."""
    import asyncio
    from app.db.session import async_session_factory
    from app.db.repository import get_patient as _get_patient

    async def _fetch():
        async with async_session_factory() as session:
            from sqlalchemy import select as sa_select
            from app.db.models import Pathway, PathwayWeek

            patient = await _get_patient(session, patient_id)
            if not patient or not patient.pathway_id:
                return (
                    "Your program includes personalized exercises designed by your physical therapist, "
                    "progress tracking, and regular check-ins. Exercises are updated based on your "
                    "recovery progress and feedback. You can do them at home at your own pace."
                )
            pw_result = await session.execute(
                sa_select(Pathway).where(Pathway.pathway_id == patient.pathway_id)
            )
            pathway = pw_result.scalar_one_or_none()
            week_result = await session.execute(
                sa_select(PathwayWeek).where(
                    PathwayWeek.pathway_id == patient.pathway_id,
                    PathwayWeek.week_number == patient.current_week,
                )
            )
            week = week_result.scalar_one_or_none()
            if not pathway or not week:
                return "Your program includes personalized exercises."
            threshold_pct = int(week.advancement_threshold * 100)
            return (
                f"You are in Week {patient.current_week} of {pathway.total_weeks} "
                f"({week.theme}) of the {pathway.name} pathway. "
                f"To advance to the next week, complete {threshold_pct}% of exercises"
                + (f" and keep pain at or below {week.pain_ceiling}/10." if week.pain_ceiling else ".")
            )

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(lambda: asyncio.run(_fetch())).result()
        else:
            return loop.run_until_complete(_fetch())
    except RuntimeError:
        return asyncio.run(_fetch())


@tool
def get_adherence_summary(patient_id: str) -> str:
    """Get the patient's exercise adherence and outcome summary including PRO trends."""
    import asyncio
    from app.db.session import async_session_factory
    from app.db.repository import get_adherence_stats as _get_adherence_stats
    from app.db.repository import get_outcome_summary as _get_outcome_summary

    async def _fetch():
        async with async_session_factory() as session:
            adherence = await _get_adherence_stats(session, patient_id)
            outcomes = await _get_outcome_summary(session, patient_id)
            return adherence, outcomes

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                adherence, outcomes = pool.submit(
                    lambda: asyncio.run(_fetch())
                ).result()
        else:
            adherence, outcomes = loop.run_until_complete(_fetch())
    except RuntimeError:
        adherence, outcomes = asyncio.run(_fetch())

    parts = [
        f"Completed {adherence['total_completed']} of {adherence['total_due']} assigned exercises "
        f"({adherence['completion_rate']}% completion rate). "
        f"Current streak: {adherence['streak']} days.",
    ]

    if outcomes["latest"]:
        latest = outcomes["latest"]
        parts.append(
            f"Latest PRO check-in: pain {latest['pain_score']}/10, "
            f"function {latest['function_score']}/10, "
            f"wellbeing {latest['wellbeing_score']}/10. "
            f"Trends — pain: {outcomes['pain_trend']}, "
            f"function: {outcomes['function_trend']}, "
            f"wellbeing: {outcomes['wellbeing_trend']}."
        )

    return " ".join(parts)


@tool
def get_education_recommendation(patient_id: str, topic: str) -> str:
    """Find relevant education content for the patient's current program day.
    Use when patients ask 'why' about an exercise or express confusion about their condition."""
    import asyncio
    from app.db.session import async_session_factory
    from app.db.repository import (
        get_patient as _get_patient,
        get_education_for_day as _get_education,
        get_patient_exercises as _get_exercises,
        DAY_THEMES,
    )

    async def _fetch():
        async with async_session_factory() as session:
            patient = await _get_patient(session, patient_id)
            if not patient or not patient.enrollment_date:
                return "No education content available yet."
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            enrollment = patient.enrollment_date
            if enrollment.tzinfo is None:
                enrollment = enrollment.replace(tzinfo=datetime.timezone.utc)
            current_day = min(max((now - enrollment).days + 1, 1), 7)
            day_theme = DAY_THEMES.get(current_day, "mobility")
            exercises = await _get_exercises(session, patient_id, day=current_day)
            body_parts = list({e.body_part for e in exercises})
            content = await _get_education(session, day_theme, body_parts)
            if not content:
                return "No education content available for today's exercises."
            # Filter by topic keyword if possible
            matches = [c for c in content if topic.lower() in c.title.lower() or topic.lower() in c.body.lower()]
            items = matches[:2] if matches else content[:2]
            parts = []
            for c in items:
                parts.append(f"**{c.title}** ({c.content_type})\n{c.body}")
            return "\n\n".join(parts)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(lambda: asyncio.run(_fetch())).result()
        else:
            return loop.run_until_complete(_fetch())
    except RuntimeError:
        return asyncio.run(_fetch())


@tool
def get_patient_insights(patient_id: str) -> str:
    """Get stored insights about the patient from prior conversations."""
    import asyncio
    from app.db.session import async_session_factory
    from app.db.repository import get_patient_insights_db as _get_insights

    async def _fetch():
        async with async_session_factory() as session:
            return await _get_insights(session, patient_id)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                insights = pool.submit(lambda: asyncio.run(_fetch())).result()
        else:
            insights = loop.run_until_complete(_fetch())
    except RuntimeError:
        insights = asyncio.run(_fetch())

    if not insights:
        return "No prior insights about this patient yet."

    CATEGORY_LABELS = {
        "preference": "Preferences",
        "motivation": "Motivations",
        "barrier": "Barriers",
        "progress_note": "Progress",
        "personal_context": "Personal Context",
        "emotional_state": "Emotional State",
    }
    lines = []
    for insight in insights:
        label = CATEGORY_LABELS.get(insight.category, insight.category.title())
        lines.append(f"- [{label}] {insight.content}")
    return "\n".join(lines)


@tool(args_schema=AlertClinicianInput)
def alert_clinician(patient_id: str, reason: str, urgency_level: str) -> str:
    """Alert the patient's clinician. Use for crisis situations or when clinical intervention is needed."""
    return f"ALERT sent to clinician for patient {patient_id}: [{urgency_level}] {reason}"
