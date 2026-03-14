import datetime
import logging
import time
from collections import OrderedDict
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import verify_api_key, verify_consent
from app.api.schemas import (
    AdherenceResponse,
    AdjustExerciseRequest,
    AdjustExerciseResponse,
    ChatRequest,
    ChatResponse,
    EducationContentResponse,
    EventTriggerRequest,
    EventTriggerResponse,
    ExerciseCompleteRequest,
    ExerciseCompleteResponse,
    ExerciseProgramResponse,
    ExerciseResponse,
    HealthResponse,
    OutcomeReportRequest,
    OutcomeReportResponse,
    OutcomeSummaryResponse,
    PathwayAdvanceResponse,
    PathwayStatusResponse,
    PatientStatusResponse,
)
from app.db.repository import (
    DAY_THEMES,
    create_outcome_report,
    find_replacement_target,
    get_active_goal,
    get_adherence_stats,
    get_education_for_day,
    get_exercise_by_id,
    get_exercise_completions,
    get_outcome_reports,
    get_outcome_summary,
    get_patient,
    get_patient_exercises,
    get_unviewed_education,
    grant_consent,
    log_audit_event,
    mark_education_viewed,
    mark_exercise_complete,
    replace_exercise,
    unmark_exercise_complete,
    update_patient_last_message,
    update_patient_phase,
)
from app.db.seed import seed_exercises
from app.db.session import get_db_session
from app.graph.parent import compiled_graph
from app.graph.state import Phase
from app.services.llm import FALLBACK_MESSAGE, get_exercise_adjustment

logger = logging.getLogger(__name__)

router = APIRouter()

# Simple idempotency cache: key -> (response, timestamp)
_idempotency_cache: OrderedDict[str, tuple[ChatResponse, float]] = OrderedDict()
IDEMPOTENCY_TTL_SECONDS = 300


def _clean_idempotency_cache() -> None:
    now = time.time()
    while _idempotency_cache:
        key, (_, ts) = next(iter(_idempotency_cache.items()))
        if now - ts > IDEMPOTENCY_TTL_SECONDS:
            _idempotency_cache.pop(key)
        else:
            break


def _calculate_tone(enrollment_date: Optional[datetime.datetime]) -> str:
    if not enrollment_date:
        return "general"
    now = datetime.datetime.now(datetime.timezone.utc)
    if enrollment_date.tzinfo is None:
        enrollment_date = enrollment_date.replace(tzinfo=datetime.timezone.utc)
    days = (now - enrollment_date).days
    if days == 2:
        return "celebration"
    elif days == 5:
        return "nudge"
    elif days == 7:
        return "check-in"
    return "general"


VALID_TRANSITIONS = {
    ("pending", "consent_granted"): "onboarding",
    ("dormant", "manual_phase_override"): "re_engaging",
}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok")


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    # Idempotency check
    if request.idempotency_key:
        _clean_idempotency_cache()
        if request.idempotency_key in _idempotency_cache:
            cached, _ = _idempotency_cache[request.idempotency_key]
            return cached

    # Verify consent
    await verify_consent(request.patient_id, session)

    patient = await get_patient(session, request.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Dormant -> Re-engaging on new message
    current_phase = patient.current_phase
    if current_phase == Phase.DORMANT:
        current_phase = Phase.RE_ENGAGING
        await update_patient_phase(session, request.patient_id, current_phase)

    tone = _calculate_tone(patient.enrollment_date)

    try:
        result = await compiled_graph.ainvoke(
            {
                "patient_id": request.patient_id,
                "current_phase": current_phase,
                "messages": [HumanMessage(content=request.message)],
                "unanswered_count": patient.unanswered_count,
                "current_goal": None,
                "tone_instruction": tone,
                "safety_retry_count": 0,
                "enrollment_date": (
                    patient.enrollment_date.isoformat()
                    if patient.enrollment_date
                    else ""
                ),
            },
            config={"configurable": {"thread_id": request.patient_id}},
        )
    except Exception:
        logger.exception("Graph invocation failed for patient %s", request.patient_id)
        return ChatResponse(
            patient_id=request.patient_id,
            response=FALLBACK_MESSAGE,
            current_phase=current_phase,
        )

    # Extract last AI message
    ai_response = FALLBACK_MESSAGE
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage):
            ai_response = msg.content
            break

    # Sync phase changes back to DB
    new_phase = result.get("current_phase", current_phase)
    if new_phase != patient.current_phase:
        await update_patient_phase(session, request.patient_id, new_phase)

    await update_patient_last_message(session, request.patient_id)

    # Load goal
    goal = await get_active_goal(session, request.patient_id)
    goal_text = result.get("current_goal") or (goal.goal_text if goal else None)

    response = ChatResponse(
        patient_id=request.patient_id,
        response=ai_response,
        current_phase=new_phase,
        current_goal=goal_text,
    )

    # Cache for idempotency
    if request.idempotency_key:
        _idempotency_cache[request.idempotency_key] = (response, time.time())

    await log_audit_event(
        session,
        request.patient_id,
        "chat",
        {"phase": new_phase, "tone": tone},
    )

    return response


@router.post("/events/trigger", response_model=EventTriggerResponse)
async def trigger_event(
    request: EventTriggerRequest,
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    if request.event_type == "consent_granted":
        patient = await get_patient(session, request.patient_id)
        if patient and patient.consent_status:
            return EventTriggerResponse(
                patient_id=request.patient_id,
                new_phase=patient.current_phase,
                message="Consent already granted",
            )
        patient = await grant_consent(session, request.patient_id)
        await seed_exercises(session, request.patient_id)
        await log_audit_event(
            session, request.patient_id, "consent_granted", {}
        )
        return EventTriggerResponse(
            patient_id=request.patient_id,
            new_phase=patient.current_phase,
            message="Consent granted, patient moved to onboarding",
        )

    # Validate transition
    patient = await get_patient(session, request.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    transition_key = (patient.current_phase, request.event_type)
    new_phase = VALID_TRANSITIONS.get(transition_key)
    if not new_phase:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid transition: {patient.current_phase} + {request.event_type}",
        )

    await update_patient_phase(session, request.patient_id, new_phase)
    await log_audit_event(
        session,
        request.patient_id,
        request.event_type,
        {"from_phase": patient.current_phase, "to_phase": new_phase},
    )

    return EventTriggerResponse(
        patient_id=request.patient_id,
        new_phase=new_phase,
        message=f"Phase transitioned to {new_phase}",
    )


@router.get("/patients/{patient_id}/status", response_model=PatientStatusResponse)
async def patient_status(
    patient_id: str,
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    goal = await get_active_goal(session, patient_id)

    return PatientStatusResponse(
        patient_id=patient_id,
        current_phase=patient.current_phase,
        current_goal=goal.goal_text if goal else None,
        unanswered_count=patient.unanswered_count,
        last_message_at=(
            patient.last_message_at.isoformat() if patient.last_message_at else None
        ),
        enrollment_date=(
            patient.enrollment_date.isoformat() if patient.enrollment_date else None
        ),
    )


@router.get(
    "/patients/{patient_id}/exercises",
    response_model=ExerciseProgramResponse,
)
async def get_exercises(
    patient_id: str,
    day: Optional[int] = Query(None, ge=1, le=7),
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Filter by current week if patient is on a pathway
    week_filter = patient.current_week if patient.pathway_id else None
    exercises = await get_patient_exercises(session, patient_id, day=day, week_number=week_filter)
    today = datetime.date.today()
    if day is not None and patient.enrollment_date is not None:
        completion_date = patient.enrollment_date.date() + datetime.timedelta(days=day - 1)
    else:
        completion_date = today
    completions = await get_exercise_completions(session, patient_id, completion_date)
    completion_map = {c.exercise_id: c for c in completions}

    exercise_responses = []
    for e in exercises:
        comp = completion_map.get(e.exercise_id)
        exercise_responses.append(
            ExerciseResponse(
                exercise_id=e.exercise_id,
                name=e.name,
                description=e.description,
                setup_instructions=e.setup_instructions,
                execution_steps=e.execution_steps,
                form_cues=e.form_cues,
                common_mistakes=e.common_mistakes,
                body_part=e.body_part,
                sets=e.sets,
                reps=e.reps,
                hold_seconds=e.hold_seconds,
                day_number=e.day_number,
                sort_order=e.sort_order,
                is_completed=comp is not None,
                sets_completed=comp.sets_completed if comp else 0,
                set_statuses=comp.set_statuses if comp else None,
                difficulty=comp.difficulty if comp else None,
                feedback=comp.feedback if comp else None,
            )
        )

    return ExerciseProgramResponse(
        patient_id=patient_id,
        day=day,
        exercises=exercise_responses,
    )


@router.post(
    "/patients/{patient_id}/exercises/complete",
    response_model=ExerciseCompleteResponse,
)
async def toggle_exercise_complete(
    patient_id: str,
    request: ExerciseCompleteRequest,
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if request.date:
        target_date = datetime.date.fromisoformat(request.date)
    else:
        target_date = datetime.date.today()

    # Get exercise to know total sets
    exercise = await get_exercise_by_id(session, request.exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    total_sets = exercise.sets

    # Derive sets_completed from set_statuses if provided
    effective_sets_completed = request.sets_completed
    if request.set_statuses is not None and effective_sets_completed is None:
        effective_sets_completed = sum(
            1 for s in request.set_statuses if s is not None
        )

    # If all statuses are null or sets_completed is explicitly 0, remove completion
    if effective_sets_completed is not None and effective_sets_completed == 0:
        await unmark_exercise_complete(
            session, patient_id, request.exercise_id, target_date
        )
        return ExerciseCompleteResponse(
            patient_id=patient_id,
            exercise_id=request.exercise_id,
            completed=False,
            date=target_date.isoformat(),
            sets_completed=0,
            set_statuses=request.set_statuses,
            total_sets=total_sets,
        )

    # Upsert completion with granular fields
    completion = await mark_exercise_complete(
        session,
        patient_id,
        request.exercise_id,
        target_date,
        sets_completed=effective_sets_completed,
        set_statuses=request.set_statuses,
        difficulty=request.difficulty,
        feedback=request.feedback,
    )

    return ExerciseCompleteResponse(
        patient_id=patient_id,
        exercise_id=request.exercise_id,
        completed=True,
        date=target_date.isoformat(),
        sets_completed=completion.sets_completed,
        set_statuses=completion.set_statuses,
        total_sets=total_sets,
    )


@router.get(
    "/patients/{patient_id}/adherence",
    response_model=AdherenceResponse,
)
async def get_adherence(
    patient_id: str,
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    stats = await get_adherence_stats(session, patient_id)
    return AdherenceResponse(patient_id=patient_id, **stats)


@router.post(
    "/patients/{patient_id}/exercises/{exercise_id}/adjust",
    response_model=AdjustExerciseResponse,
)
async def adjust_exercise(
    patient_id: str,
    exercise_id: int,
    request: AdjustExerciseRequest,
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    exercise = await get_exercise_by_id(session, exercise_id)
    if not exercise or exercise.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Exercise not found")

    if request.difficulty not in ("too_easy", "too_hard"):
        raise HTTPException(
            status_code=422, detail="difficulty must be 'too_easy' or 'too_hard'"
        )

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
        difficulty=request.difficulty,
        feedback=request.feedback,
        set_statuses=source_set_statuses,
    )

    # Find replacement target on a different day (source stays unchanged)
    target = await find_replacement_target(
        session, patient_id, exercise, current_day
    )

    if target:
        target_exercise_id = target.exercise_id
        target_day = target.day_number
        target_exercise_name = target.name
    else:
        # Tier 3: create on next day
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
        # No existing target; create a new exercise on the target day
        from app.db.models import Exercise as ExerciseModel

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

    day_label = f"Day {target_day}"
    if target_day <= current_day:
        day_label += " (next cycle)"

    original_response = ExerciseResponse(
        exercise_id=exercise.exercise_id,
        name=exercise.name,
        description=exercise.description,
        body_part=exercise.body_part,
        sets=exercise.sets,
        reps=exercise.reps,
        hold_seconds=exercise.hold_seconds,
        day_number=exercise.day_number,
        sort_order=exercise.sort_order,
        is_completed=source_comp is not None,
        sets_completed=source_comp.sets_completed if source_comp else 0,
        set_statuses=source_set_statuses,
    )

    new_response = ExerciseResponse(
        exercise_id=new_exercise.exercise_id,
        name=new_exercise.name,
        description=new_exercise.description,
        body_part=new_exercise.body_part,
        sets=new_exercise.sets,
        reps=new_exercise.reps,
        hold_seconds=new_exercise.hold_seconds,
        day_number=new_exercise.day_number,
        sort_order=new_exercise.sort_order,
        is_completed=False,
    )

    replaced_name = target_exercise_name or f"new slot on {day_label}"
    reasoning_with_day = (
        f"{day_label}: {replaced_name} → {new_exercise.name}. "
        f"{adjustment['reasoning']}"
    )

    await log_audit_event(
        session,
        patient_id,
        "exercise_adjusted",
        {
            "source_exercise_id": exercise_id,
            "target_exercise_id": target.exercise_id if target else None,
            "new_exercise_id": new_exercise.exercise_id,
            "target_day": target_day,
            "difficulty": request.difficulty,
            "reasoning": adjustment["reasoning"],
        },
    )

    return AdjustExerciseResponse(
        original_exercise=original_response,
        new_exercise=new_response,
        reasoning=reasoning_with_day,
        target_day=target_day,
        target_exercise_name=target_exercise_name,
    )


# ── PRO (Patient-Reported Outcomes) endpoints ────────────────────────────────


@router.post(
    "/patients/{patient_id}/outcomes",
    response_model=OutcomeReportResponse,
    status_code=201,
)
async def submit_outcome_report(
    patient_id: str,
    request: OutcomeReportRequest,
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    report = await create_outcome_report(
        session,
        patient_id,
        pain_score=request.pain_score,
        function_score=request.function_score,
        wellbeing_score=request.wellbeing_score,
        notes=request.notes,
    )

    return OutcomeReportResponse(
        report_id=report.report_id,
        patient_id=report.patient_id,
        report_date=report.report_date.isoformat(),
        pain_score=report.pain_score,
        function_score=report.function_score,
        wellbeing_score=report.wellbeing_score,
        notes=report.notes,
    )


@router.get(
    "/patients/{patient_id}/outcomes",
    response_model=OutcomeSummaryResponse,
)
async def get_outcomes(
    patient_id: str,
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    summary = await get_outcome_summary(session, patient_id)
    reports = await get_outcome_reports(session, patient_id)

    latest_resp = None
    if summary["latest"]:
        latest_resp = OutcomeReportResponse(**summary["latest"])

    report_responses = [
        OutcomeReportResponse(
            report_id=r.report_id,
            patient_id=r.patient_id,
            report_date=r.report_date.isoformat(),
            pain_score=r.pain_score,
            function_score=r.function_score,
            wellbeing_score=r.wellbeing_score,
            notes=r.notes,
        )
        for r in reports
    ]

    return OutcomeSummaryResponse(
        patient_id=patient_id,
        latest=latest_resp,
        pain_trend=summary["pain_trend"],
        function_trend=summary["function_trend"],
        wellbeing_trend=summary["wellbeing_trend"],
        report_count=summary["report_count"],
        reports=report_responses,
    )


# ── Education Content endpoints ──────────────────────────────────────────────


@router.get(
    "/patients/{patient_id}/education",
    response_model=list,
)
async def get_education(
    patient_id: str,
    day: int = Query(ge=1, le=7),
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    day_theme = DAY_THEMES.get(day)
    if not day_theme:
        return []

    # Get body parts for this day's exercises
    exercises = await get_patient_exercises(session, patient_id, day=day)
    body_parts = list({e.body_part for e in exercises})

    content = await get_education_for_day(session, day_theme, body_parts)
    if not content:
        return []

    content_ids = [c.content_id for c in content]
    unviewed_ids = await get_unviewed_education(session, patient_id, content_ids)

    return [
        EducationContentResponse(
            content_id=c.content_id,
            title=c.title,
            body=c.body,
            content_type=c.content_type,
            body_part=c.body_part,
            is_viewed=c.content_id not in unviewed_ids,
        )
        for c in content
    ]


@router.post(
    "/patients/{patient_id}/education/{content_id}/view",
    status_code=204,
)
async def view_education(
    patient_id: str,
    content_id: int,
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    await mark_education_viewed(session, patient_id, content_id)


# ── Pathway endpoints ────────────────────────────────────────────────────────


@router.get(
    "/patients/{patient_id}/pathway",
    response_model=PathwayStatusResponse,
)
async def get_pathway_status(
    patient_id: str,
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    from app.db.models import Pathway, PathwayWeek

    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if not patient.pathway_id:
        return PathwayStatusResponse(
            patient_id=patient_id,
            pathway_name=None,
            current_week=1,
            total_weeks=1,
            week_theme="Standard",
            advancement_threshold=0.0,
            current_adherence=0.0,
            can_advance=False,
            blocker=None,
        )

    from sqlalchemy import select as sa_select

    pathway_result = await session.execute(
        sa_select(Pathway).where(Pathway.pathway_id == patient.pathway_id)
    )
    pathway = pathway_result.scalar_one_or_none()

    week_result = await session.execute(
        sa_select(PathwayWeek).where(
            PathwayWeek.pathway_id == patient.pathway_id,
            PathwayWeek.week_number == patient.current_week,
        )
    )
    current_pw = week_result.scalar_one_or_none()

    adherence = await get_adherence_stats(session, patient_id, week_number=patient.current_week)
    completion_rate = adherence["completion_rate"]
    threshold = current_pw.advancement_threshold if current_pw else 0.0

    # Check advancement eligibility without side effects
    can_advance = False
    blocker = None
    if patient.current_week >= (pathway.total_weeks if pathway else 1):
        blocker = "already_final_week"
    elif (completion_rate / 100.0) < threshold:
        blocker = "adherence"
    else:
        # Check pain ceiling
        if current_pw and current_pw.pain_ceiling is not None:
            outcomes = await get_outcome_summary(session, patient_id)
            if outcomes["latest"] and outcomes["latest"]["pain_score"] > current_pw.pain_ceiling:
                blocker = "pain"
            else:
                can_advance = True
        else:
            can_advance = True

    return PathwayStatusResponse(
        patient_id=patient_id,
        pathway_name=pathway.name if pathway else None,
        current_week=patient.current_week,
        total_weeks=pathway.total_weeks if pathway else 1,
        week_theme=current_pw.theme if current_pw else "Unknown",
        advancement_threshold=threshold,
        current_adherence=completion_rate,
        can_advance=can_advance,
        blocker=blocker,
    )


@router.post(
    "/patients/{patient_id}/pathway/advance",
    response_model=PathwayAdvanceResponse,
)
async def advance_pathway(
    patient_id: str,
    _api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    from app.services.pathway import evaluate_advancement
    result = await evaluate_advancement(session, patient_id)

    return PathwayAdvanceResponse(
        advanced=result["advanced"],
        new_week=result["new_week"],
        reason=result["reason"],
    )
