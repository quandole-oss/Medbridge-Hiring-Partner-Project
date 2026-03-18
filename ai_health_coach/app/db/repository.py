import datetime
from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuditLog,
    DailyBriefing,
    EducationContent,
    EducationView,
    Exercise,
    ExerciseCompletion,
    Goal,
    OutcomeReport,
    Patient,
    PatientInsight,
)


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
    session: AsyncSession,
    patient_id: str,
    goal_text: str,
    target_date: Optional[datetime.date] = None,
) -> Goal:
    goal = Goal(patient_id=patient_id, goal_text=goal_text, target_date=target_date)
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


async def get_active_goals(session: AsyncSession, patient_id: str) -> List[Goal]:
    result = await session.execute(
        select(Goal)
        .where(Goal.patient_id == patient_id, Goal.is_active == True)
        .order_by(Goal.created_at.asc())
    )
    return list(result.scalars().all())


async def update_goal(
    session: AsyncSession,
    goal_id: int,
    goal_text: Optional[str] = None,
    target_date: Optional[datetime.date] = None,
    is_active: Optional[bool] = None,
) -> Optional[Goal]:
    result = await session.execute(
        select(Goal).where(Goal.goal_id == goal_id)
    )
    goal = result.scalar_one_or_none()
    if not goal:
        return None
    if goal_text is not None:
        goal.goal_text = goal_text
    if target_date is not None:
        goal.target_date = target_date
    if is_active is not None:
        goal.is_active = is_active
    await session.commit()
    await session.refresh(goal)
    return goal


async def deactivate_goal(session: AsyncSession, goal_id: int) -> Optional[Goal]:
    return await update_goal(session, goal_id, is_active=False)


async def get_exercises_by_goal(
    session: AsyncSession, patient_id: str, goal_id: int
) -> List[Exercise]:
    result = await session.execute(
        select(Exercise).where(
            Exercise.patient_id == patient_id,
            Exercise.goal_id == goal_id,
            Exercise.is_active == True,
        ).order_by(Exercise.day_number, Exercise.sort_order)
    )
    return list(result.scalars().all())


async def get_daily_exercise_counts(
    session: AsyncSession, patient_id: str
) -> dict:
    """Return {day_number: count} for active exercises."""
    result = await session.execute(
        select(Exercise.day_number, func.count(Exercise.exercise_id))
        .where(Exercise.patient_id == patient_id, Exercise.is_active == True)
        .group_by(Exercise.day_number)
    )
    return {row[0]: row[1] for row in result.all()}


async def bulk_create_exercises(
    session: AsyncSession, patient_id: str, exercises_data: List[dict]
) -> List[Exercise]:
    exercises = []
    for data in exercises_data:
        exercise = Exercise(patient_id=patient_id, **data)
        session.add(exercise)
        exercises.append(exercise)
    await session.commit()
    for e in exercises:
        await session.refresh(e)
    return exercises


async def deactivate_exercises_for_goal(
    session: AsyncSession, patient_id: str, goal_id: int
) -> int:
    result = await session.execute(
        select(Exercise).where(
            Exercise.patient_id == patient_id,
            Exercise.goal_id == goal_id,
            Exercise.is_active == True,
        )
    )
    exercises = list(result.scalars().all())
    count = 0
    for ex in exercises:
        ex.is_active = False
        count += 1
    await session.commit()
    return count


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


async def get_patient_exercises(
    session: AsyncSession,
    patient_id: str,
    day: Optional[int] = None,
    week_number: Optional[int] = None,
) -> List[Exercise]:
    stmt = select(Exercise).where(
        Exercise.patient_id == patient_id, Exercise.is_active == True
    )
    if day is not None:
        stmt = stmt.where(Exercise.day_number == day)
    if week_number is not None:
        stmt = stmt.where(Exercise.week_number == week_number)
    stmt = stmt.order_by(Exercise.day_number, Exercise.sort_order)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_exercise_completions(
    session: AsyncSession, patient_id: str, date: datetime.date
) -> List[ExerciseCompletion]:
    result = await session.execute(
        select(ExerciseCompletion).where(
            ExerciseCompletion.patient_id == patient_id,
            ExerciseCompletion.completed_date == date,
        )
    )
    return list(result.scalars().all())


async def mark_exercise_complete(
    session: AsyncSession,
    patient_id: str,
    exercise_id: int,
    date: datetime.date,
    sets_completed: Optional[int] = None,
    set_statuses: Optional[list] = None,
    difficulty: Optional[str] = None,
    feedback: Optional[str] = None,
) -> ExerciseCompletion:
    # Derive sets_completed from set_statuses if provided
    if set_statuses is not None and sets_completed is None:
        sets_completed = sum(1 for s in set_statuses if s is not None)

    result = await session.execute(
        select(ExerciseCompletion).where(
            ExerciseCompletion.patient_id == patient_id,
            ExerciseCompletion.exercise_id == exercise_id,
            ExerciseCompletion.completed_date == date,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        if sets_completed is not None:
            existing.sets_completed = sets_completed
        if set_statuses is not None:
            existing.set_statuses = set_statuses
        if difficulty is not None:
            existing.difficulty = difficulty
        if feedback is not None:
            existing.feedback = feedback
        await session.commit()
        await session.refresh(existing)
        return existing
    completion = ExerciseCompletion(
        patient_id=patient_id,
        exercise_id=exercise_id,
        completed_date=date,
        sets_completed=sets_completed or 0,
        set_statuses=set_statuses,
        difficulty=difficulty,
        feedback=feedback,
    )
    session.add(completion)
    await session.commit()
    await session.refresh(completion)
    return completion


async def unmark_exercise_complete(
    session: AsyncSession,
    patient_id: str,
    exercise_id: int,
    date: datetime.date,
) -> None:
    await session.execute(
        delete(ExerciseCompletion).where(
            ExerciseCompletion.patient_id == patient_id,
            ExerciseCompletion.exercise_id == exercise_id,
            ExerciseCompletion.completed_date == date,
        )
    )
    await session.commit()


async def get_adherence_stats(
    session: AsyncSession, patient_id: str, week_number: Optional[int] = None
) -> dict:
    patient = await get_patient(session, patient_id)
    if not patient or not patient.enrollment_date:
        return {
            "days_in_program": 0,
            "current_day": 1,
            "total_completed": 0,
            "total_due": 0,
            "completion_rate": 0.0,
            "streak": 0,
            "milestones": {"2": False, "5": False, "7": False},
            "exercises_completed_today": 0,
            "exercises_due_today": 0,
            "daily_completions": [],
        }

    now = datetime.datetime.now(datetime.timezone.utc)
    enrollment = patient.enrollment_date
    if enrollment.tzinfo is None:
        enrollment = enrollment.replace(tzinfo=datetime.timezone.utc)
    days_in_program = max((now - enrollment).days + 1, 1)
    current_day = min(days_in_program, 7)

    # Total exercises due (days completed so far)
    due_stmt = select(func.count(Exercise.exercise_id)).where(
        Exercise.patient_id == patient_id,
        Exercise.is_active == True,
        Exercise.day_number <= current_day,
    )
    if week_number is not None:
        due_stmt = due_stmt.where(Exercise.week_number == week_number)
    due_result = await session.execute(due_stmt)
    total_due = due_result.scalar() or 0

    # Total completed
    comp_stmt = select(func.count(ExerciseCompletion.completion_id)).where(
        ExerciseCompletion.patient_id == patient_id,
    )
    if week_number is not None:
        # Join to Exercise to filter by week
        comp_stmt = (
            select(func.count(ExerciseCompletion.completion_id))
            .join(Exercise, ExerciseCompletion.exercise_id == Exercise.exercise_id)
            .where(
                ExerciseCompletion.patient_id == patient_id,
                Exercise.week_number == week_number,
            )
        )
    completed_result = await session.execute(comp_stmt)
    total_completed = completed_result.scalar() or 0

    completion_rate = (total_completed / total_due * 100) if total_due > 0 else 0.0

    # Today's stats
    today = now.date()
    today_exercises = await get_patient_exercises(session, patient_id, day=current_day)
    today_completions = await get_exercise_completions(session, patient_id, today)
    completed_ids_today = {c.exercise_id for c in today_completions}
    exercises_due_today = len(today_exercises)
    exercises_completed_today = sum(
        1 for e in today_exercises if e.exercise_id in completed_ids_today
    )

    # Streak: count consecutive days with at least one assigned exercise completed
    # (today is still in progress so it shouldn't break the streak)
    streak = 0
    for d in range(current_day - 1, 0, -1):
        check_date = today - datetime.timedelta(days=current_day - d)
        day_exercises = await get_patient_exercises(session, patient_id, day=d)
        if not day_exercises:
            break
        day_completions = await get_exercise_completions(
            session, patient_id, check_date
        )
        day_completed_ids = {c.exercise_id for c in day_completions}
        if any(e.exercise_id in day_completed_ids for e in day_exercises):
            streak += 1
        else:
            break

    # Milestones
    milestones = {
        "2": days_in_program >= 2,
        "5": days_in_program >= 5,
        "7": days_in_program >= 7,
    }

    # Daily completions for chart
    daily_completions = []
    for d in range(1, 8):
        day_exs = await get_patient_exercises(session, patient_id, day=d)
        check_date = today - datetime.timedelta(days=current_day - d)
        if d <= current_day and day_exs:
            day_comps = await get_exercise_completions(
                session, patient_id, check_date
            )
            comp_ids = {c.exercise_id for c in day_comps}
            done = sum(1 for e in day_exs if e.exercise_id in comp_ids)
            daily_completions.append(
                {"day": d, "completed": done, "total": len(day_exs)}
            )
        else:
            daily_completions.append(
                {"day": d, "completed": 0, "total": len(day_exs)}
            )

    return {
        "days_in_program": days_in_program,
        "current_day": current_day,
        "total_completed": total_completed,
        "total_due": total_due,
        "completion_rate": round(completion_rate, 1),
        "streak": streak,
        "milestones": milestones,
        "exercises_completed_today": exercises_completed_today,
        "exercises_due_today": exercises_due_today,
        "daily_completions": daily_completions,
    }


async def get_exercise_by_id(
    session: AsyncSession, exercise_id: int
) -> Optional[Exercise]:
    result = await session.execute(
        select(Exercise).where(Exercise.exercise_id == exercise_id)
    )
    return result.scalar_one_or_none()


async def find_replacement_target(
    session: AsyncSession,
    patient_id: str,
    source_exercise: Exercise,
    current_day: int,
) -> Optional[Exercise]:
    """Three-tier fallback to find a replacement target on a different day.

    1. Same exercise name on a later day
    2. Same body_part exercise on nearest future day
    3. No match -> returns None (caller creates on next day)
    """
    # Tier 1: Same name on a later day (wraps around)
    all_exercises = await get_patient_exercises(session, patient_id)
    candidates = [
        e for e in all_exercises
        if e.name == source_exercise.name
        and e.day_number != current_day
        and e.exercise_id != source_exercise.exercise_id
    ]
    if candidates:
        # Prefer future days, then wrap
        future = [e for e in candidates if e.day_number > current_day]
        if future:
            future.sort(key=lambda e: e.day_number)
            return future[0]
        candidates.sort(key=lambda e: e.day_number)
        return candidates[0]

    # Tier 2: Same body_part on a different day
    body_candidates = [
        e for e in all_exercises
        if e.body_part == source_exercise.body_part
        and e.day_number != current_day
        and e.exercise_id != source_exercise.exercise_id
    ]
    if body_candidates:
        future = [e for e in body_candidates if e.day_number > current_day]
        if future:
            future.sort(key=lambda e: e.day_number)
            return future[0]
        body_candidates.sort(key=lambda e: e.day_number)
        return body_candidates[0]

    # Tier 3: No match
    return None


async def replace_exercise(
    session: AsyncSession,
    patient_id: str,
    old_exercise_id: int,
    name: str,
    description: str,
    body_part: str,
    sets: int,
    reps: int,
    hold_seconds: Optional[int] = None,
) -> Exercise:
    old_exercise = await get_exercise_by_id(session, old_exercise_id)
    if not old_exercise:
        raise ValueError(f"Exercise {old_exercise_id} not found")

    new_exercise = Exercise(
        patient_id=patient_id,
        name=name,
        description=description,
        body_part=body_part,
        sets=sets,
        reps=reps,
        hold_seconds=hold_seconds,
        day_number=old_exercise.day_number,
        sort_order=old_exercise.sort_order,
        is_active=True,
    )
    session.add(new_exercise)
    await session.flush()

    old_exercise.is_active = False
    old_exercise.replaced_by_id = new_exercise.exercise_id

    await session.commit()
    await session.refresh(new_exercise)
    return new_exercise


# ── Outcome Reports (PROs) ──────────────────────────────────────────────────


async def create_outcome_report(
    session: AsyncSession,
    patient_id: str,
    pain_score: int,
    function_score: int,
    wellbeing_score: int,
    notes: Optional[str] = None,
) -> OutcomeReport:
    report = OutcomeReport(
        patient_id=patient_id,
        report_date=datetime.date.today(),
        pain_score=pain_score,
        function_score=function_score,
        wellbeing_score=wellbeing_score,
        notes=notes,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def get_outcome_reports(
    session: AsyncSession, patient_id: str, limit: int = 10
) -> List[OutcomeReport]:
    result = await session.execute(
        select(OutcomeReport)
        .where(OutcomeReport.patient_id == patient_id)
        .order_by(OutcomeReport.report_date.desc(), OutcomeReport.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_outcome_summary(
    session: AsyncSession, patient_id: str
) -> dict:
    reports = await get_outcome_reports(session, patient_id, limit=100)
    if not reports:
        return {
            "latest": None,
            "pain_trend": "stable",
            "function_trend": "stable",
            "wellbeing_trend": "stable",
            "report_count": 0,
        }

    latest = reports[0]  # most recent

    def compute_trend(scores: List[int]) -> str:
        """Compute trend from newest-first scores. 'improving' = scores going up."""
        if len(scores) < 2:
            return "stable"
        # scores[0] is most recent; compare first half (recent) vs second half (older)
        mid = len(scores) // 2
        recent_avg = sum(scores[:mid]) / mid
        older_avg = sum(scores[mid:]) / len(scores[mid:])
        delta = recent_avg - older_avg
        if abs(delta) < 0.5:
            return "stable"
        return "improving" if delta > 0 else "declining"

    # Reports are newest-first; for pain, lower is better so invert
    pain_scores = [r.pain_score for r in reports]
    function_scores = [r.function_score for r in reports]
    wellbeing_scores = [r.wellbeing_score for r in reports]

    pain_trend_raw = compute_trend(pain_scores)
    # Invert pain trend: decreasing pain = improving
    pain_trend = (
        "improving" if pain_trend_raw == "declining"
        else "declining" if pain_trend_raw == "improving"
        else "stable"
    )

    return {
        "latest": {
            "report_id": latest.report_id,
            "patient_id": latest.patient_id,
            "report_date": latest.report_date.isoformat(),
            "pain_score": latest.pain_score,
            "function_score": latest.function_score,
            "wellbeing_score": latest.wellbeing_score,
            "notes": latest.notes,
        },
        "pain_trend": pain_trend,
        "function_trend": compute_trend(function_scores),
        "wellbeing_trend": compute_trend(wellbeing_scores),
        "report_count": len(reports),
    }


# ── Education Content ────────────────────────────────────────────────────────


DAY_THEMES = {
    1: "mobility",
    2: "stretching",
    3: "strengthening",
    4: "balance",
    5: "strength_progression",
    6: "flexibility",
    7: "full_circuit",
}


async def get_education_for_day(
    session: AsyncSession,
    day_theme: str,
    body_parts: List[str],
) -> List[EducationContent]:
    stmt = (
        select(EducationContent)
        .where(
            EducationContent.is_active == True,
            (
                (EducationContent.day_theme == day_theme)
                | (EducationContent.body_part.in_(body_parts))
            ),
        )
        .order_by(EducationContent.sort_order)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_unviewed_education(
    session: AsyncSession,
    patient_id: str,
    content_ids: List[int],
) -> List[int]:
    if not content_ids:
        return []
    result = await session.execute(
        select(EducationView.content_id).where(
            EducationView.patient_id == patient_id,
            EducationView.content_id.in_(content_ids),
        )
    )
    viewed = {row[0] for row in result.all()}
    return [cid for cid in content_ids if cid not in viewed]


async def mark_education_viewed(
    session: AsyncSession,
    patient_id: str,
    content_id: int,
) -> EducationView:
    # Check if already viewed
    result = await session.execute(
        select(EducationView).where(
            EducationView.patient_id == patient_id,
            EducationView.content_id == content_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    view = EducationView(patient_id=patient_id, content_id=content_id)
    session.add(view)
    await session.commit()
    await session.refresh(view)
    return view


# ── Patient Insights (Adaptive Memory) ───────────────────────────────────────


async def get_patient_insights_db(
    session: AsyncSession,
    patient_id: str,
    min_confidence: float = 0.3,
    limit: int = 10,
) -> List[PatientInsight]:
    result = await session.execute(
        select(PatientInsight)
        .where(
            PatientInsight.patient_id == patient_id,
            PatientInsight.is_active == True,
            PatientInsight.confidence >= min_confidence,
        )
        .order_by(
            PatientInsight.confidence.desc(),
            PatientInsight.last_reinforced_at.desc().nulls_last(),
            PatientInsight.created_at.desc(),
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def upsert_patient_insight(
    session: AsyncSession,
    patient_id: str,
    category: str,
    content: str,
) -> PatientInsight:
    result = await session.execute(
        select(PatientInsight).where(
            PatientInsight.patient_id == patient_id,
            PatientInsight.category == category,
            PatientInsight.content == content,
            PatientInsight.is_active == True,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.confidence = min(existing.confidence + 0.1, 1.0)
        existing.times_reinforced += 1
        existing.last_reinforced_at = datetime.datetime.now(datetime.timezone.utc)
        await session.commit()
        await session.refresh(existing)
        return existing

    insight = PatientInsight(
        patient_id=patient_id,
        category=category,
        content=content,
        confidence=0.7,
    )
    session.add(insight)
    await session.commit()
    await session.refresh(insight)
    return insight


async def decay_unreinforced_insights(
    session: AsyncSession,
    patient_id: str,
    reinforced_ids: List[int],
    decay_amount: float = 0.05,
) -> None:
    stmt = select(PatientInsight).where(
        PatientInsight.patient_id == patient_id,
        PatientInsight.is_active == True,
    )
    if reinforced_ids:
        stmt = stmt.where(PatientInsight.insight_id.notin_(reinforced_ids))

    result = await session.execute(stmt)
    insights = list(result.scalars().all())

    for insight in insights:
        insight.confidence = round(insight.confidence - decay_amount, 4)
        if insight.confidence < 0.1:
            insight.is_active = False

    await session.commit()


# ── Exercise Difficulty Signals ───────────────────────────────────────────────


async def get_recent_difficulty_signals(
    session: AsyncSession,
    patient_id: str,
    exercise_id: int,
    days: int = 3,
    signal: str = "too_hard",
) -> List[ExerciseCompletion]:
    """Completions with a specific difficulty for an exercise in last N days."""
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    result = await session.execute(
        select(ExerciseCompletion).where(
            ExerciseCompletion.patient_id == patient_id,
            ExerciseCompletion.exercise_id == exercise_id,
            ExerciseCompletion.difficulty == signal,
            ExerciseCompletion.completed_date >= cutoff,
        ).order_by(ExerciseCompletion.completed_date.desc())
    )
    return list(result.scalars().all())


async def get_difficulty_pattern_summary(
    session: AsyncSession,
    patient_id: str,
    days: int = 7,
) -> dict:
    """Aggregate difficulty feedback: {"too_hard": 3, "too_easy": 1, "just_right": 8, "no_feedback": 4}"""
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    result = await session.execute(
        select(ExerciseCompletion).where(
            ExerciseCompletion.patient_id == patient_id,
            ExerciseCompletion.completed_date >= cutoff,
        )
    )
    completions = list(result.scalars().all())
    summary = {"too_hard": 0, "too_easy": 0, "just_right": 0, "no_feedback": 0}
    for c in completions:
        if c.difficulty in summary:
            summary[c.difficulty] += 1
        else:
            summary["no_feedback"] += 1
    return summary


# ── Daily Briefing ────────────────────────────────────────────────────────────


async def get_daily_briefing(
    session: AsyncSession,
    patient_id: str,
    date: datetime.date,
) -> Optional[DailyBriefing]:
    result = await session.execute(
        select(DailyBriefing).where(
            DailyBriefing.patient_id == patient_id,
            DailyBriefing.briefing_date == date,
        )
    )
    return result.scalar_one_or_none()


async def save_daily_briefing(
    session: AsyncSession,
    patient_id: str,
    date: datetime.date,
    message: str,
) -> DailyBriefing:
    briefing = DailyBriefing(
        patient_id=patient_id,
        briefing_date=date,
        message=message,
    )
    session.add(briefing)
    await session.commit()
    await session.refresh(briefing)
    return briefing
