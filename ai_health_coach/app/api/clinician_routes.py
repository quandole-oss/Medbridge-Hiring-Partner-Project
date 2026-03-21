import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import verify_clinician
from app.api.schemas import (
    AdherenceHeatmapCell,
    AdherenceHeatmapResponse,
    AdherenceResponse,
    AlertCountResponse,
    AlertResponse,
    AuditEventResponse,
    CaseloadBriefingResponse,
    DailyCompletion,
    GoalResponse,
    OutcomeReportResponse,
    OutcomeSummaryResponse,
    OutcomeTrendsResponse,
    PatientAISummaryResponse,
    PatientDetailResponse,
    PatientInsightResponse,
    PatientOutcomeTrend,
    PatientOverviewItem,
    PatientOverviewResponse,
    UpdateAlertRequest,
)
from app.db.models import Clinician
from app.db.repository import (
    count_open_alerts,
    get_active_goals,
    get_adherence_heatmap_data,
    get_adherence_stats,
    get_alert_by_id,
    get_alerts,
    get_all_outcome_trends,
    get_all_patients,
    get_difficulty_pattern_summary,
    get_outcome_reports,
    get_outcome_summary,
    get_patient,
    get_patient_audit_log,
    get_patient_insights_db,
    update_alert_status,
)
from app.db.session import get_db_session

clinician_router = APIRouter(prefix="/clinician", tags=["clinician"])


def _format_dt(dt_val: Optional[datetime.datetime]) -> Optional[str]:
    if dt_val is None:
        return None
    return dt_val.isoformat()


def _alert_to_response(alert) -> AlertResponse:
    return AlertResponse(
        alert_id=alert.alert_id,
        patient_id=alert.patient_id,
        alert_type=alert.alert_type,
        urgency=alert.urgency,
        reason=alert.reason,
        status=alert.status,
        context=alert.context,
        created_at=_format_dt(alert.created_at) or "",
        acknowledged_at=_format_dt(alert.acknowledged_at),
        resolved_at=_format_dt(alert.resolved_at),
        resolved_note=alert.resolved_note,
    )


# ── Alerts ───────────────────────────────────────────────────────────────────


@clinician_router.get("/alerts", response_model=list)
async def list_alerts(
    status: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    clinician: Clinician = Depends(verify_clinician),
    session: AsyncSession = Depends(get_db_session),
):
    alerts = await get_alerts(session, status=status, urgency=urgency,
                              patient_id=patient_id, limit=limit, offset=offset)
    return [_alert_to_response(a) for a in alerts]


@clinician_router.get("/alerts/counts", response_model=AlertCountResponse)
async def alert_counts(
    clinician: Clinician = Depends(verify_clinician),
    session: AsyncSession = Depends(get_db_session),
):
    counts = await count_open_alerts(session)
    return AlertCountResponse(**counts)


@clinician_router.patch("/alerts/{alert_id}", response_model=AlertResponse)
async def patch_alert(
    alert_id: int,
    request: UpdateAlertRequest,
    clinician: Clinician = Depends(verify_clinician),
    session: AsyncSession = Depends(get_db_session),
):
    if request.status not in ("acknowledged", "resolved", "dismissed"):
        raise HTTPException(status_code=400, detail="Invalid status")
    alert = await update_alert_status(
        session, alert_id, request.status, request.resolved_note
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _alert_to_response(alert)


# ── Patients ─────────────────────────────────────────────────────────────────


@clinician_router.get("/patients", response_model=PatientOverviewResponse)
async def list_patients(
    phase: Optional[str] = Query(None),
    clinician: Clinician = Depends(verify_clinician),
    session: AsyncSession = Depends(get_db_session),
):
    patients = await get_all_patients(session, phase=phase)
    items = []
    now = datetime.datetime.now(datetime.timezone.utc)
    for p in patients:
        adherence = await get_adherence_stats(session, p.patient_id)
        goals = await get_active_goals(session, p.patient_id)
        p_alerts = await get_alerts(session, status="open", patient_id=p.patient_id)
        outcome = await get_outcome_summary(session, p.patient_id)

        days_since = None
        if p.last_message_at:
            lm = p.last_message_at
            if lm.tzinfo is None:
                lm = lm.replace(tzinfo=datetime.timezone.utc)
            days_since = (now - lm).days

        latest_pain = None
        pain_trend = "stable"
        if outcome.get("latest"):
            latest_pain = outcome["latest"].get("pain_score")
            pain_trend = outcome.get("pain_trend", "stable")

        items.append(PatientOverviewItem(
            patient_id=p.patient_id,
            current_phase=p.current_phase,
            enrollment_date=_format_dt(p.enrollment_date),
            last_message_at=_format_dt(p.last_message_at),
            days_since_last_message=days_since,
            open_alert_count=len(p_alerts),
            completion_rate=adherence.get("completion_rate", 0.0),
            latest_pain_score=latest_pain,
            pain_trend=pain_trend,
            active_goal_count=len(goals),
        ))

    return PatientOverviewResponse(patients=items, total=len(items))


@clinician_router.get("/patients/{patient_id}", response_model=PatientDetailResponse)
async def get_patient_detail(
    patient_id: str,
    clinician: Clinician = Depends(verify_clinician),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    goals = await get_active_goals(session, patient_id)
    adherence = await get_adherence_stats(session, patient_id)
    outcome_summary = await get_outcome_summary(session, patient_id)
    outcome_reports = await get_outcome_reports(session, patient_id)
    alerts = await get_alerts(session, status="open", patient_id=patient_id)
    audit_events = await get_patient_audit_log(session, patient_id, limit=10)
    difficulty = await get_difficulty_pattern_summary(session, patient_id)
    insights = await get_patient_insights_db(session, patient_id)

    # Build goal responses
    goal_responses = []
    for g in goals:
        goal_responses.append(GoalResponse(
            goal_id=g.goal_id,
            goal_text=g.goal_text,
            target_date=g.target_date.isoformat() if g.target_date else None,
            is_active=g.is_active,
            created_at=g.created_at.isoformat() if g.created_at else "",
        ))

    # Build adherence response
    adherence_resp = AdherenceResponse(
        patient_id=patient_id,
        days_in_program=adherence["days_in_program"],
        current_day=adherence["current_day"],
        total_completed=adherence["total_completed"],
        total_due=adherence["total_due"],
        completion_rate=adherence["completion_rate"],
        streak=adherence["streak"],
        milestones=adherence["milestones"],
        exercises_completed_today=adherence["exercises_completed_today"],
        exercises_due_today=adherence["exercises_due_today"],
        daily_completions=[
            DailyCompletion(**dc) for dc in adherence["daily_completions"]
        ],
    )

    # Build outcome summary response
    latest_resp = None
    if outcome_summary["latest"]:
        latest_resp = OutcomeReportResponse(**outcome_summary["latest"])
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
        for r in outcome_reports
    ]
    outcome_resp = OutcomeSummaryResponse(
        patient_id=patient_id,
        latest=latest_resp,
        pain_trend=outcome_summary["pain_trend"],
        function_trend=outcome_summary["function_trend"],
        wellbeing_trend=outcome_summary["wellbeing_trend"],
        report_count=outcome_summary["report_count"],
        reports=report_responses,
    )

    return PatientDetailResponse(
        patient_id=patient_id,
        current_phase=patient.current_phase,
        enrollment_date=_format_dt(patient.enrollment_date),
        last_message_at=_format_dt(patient.last_message_at),
        goals=goal_responses,
        adherence=adherence_resp,
        outcome_summary=outcome_resp,
        open_alerts=[_alert_to_response(a) for a in alerts],
        recent_audit_events=[
            AuditEventResponse(
                log_id=e.log_id,
                event_type=e.event_type,
                payload=e.payload,
                timestamp=e.timestamp.isoformat() if e.timestamp else "",
            )
            for e in audit_events
        ],
        difficulty_summary=difficulty,
        insights=[
            PatientInsightResponse(
                category=i.category,
                content=i.content,
                confidence=i.confidence,
                times_reinforced=i.times_reinforced,
            )
            for i in insights
        ],
    )


# ── Audit Log ────────────────────────────────────────────────────────────────


@clinician_router.get(
    "/patients/{patient_id}/audit-log", response_model=list
)
async def patient_audit_log(
    patient_id: str,
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    clinician: Clinician = Depends(verify_clinician),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    events = await get_patient_audit_log(
        session, patient_id, event_type=event_type, limit=limit, offset=offset
    )
    return [
        AuditEventResponse(
            log_id=e.log_id,
            event_type=e.event_type,
            payload=e.payload,
            timestamp=e.timestamp.isoformat() if e.timestamp else "",
        )
        for e in events
    ]


# ── Cross-Patient Analytics ──────────────────────────────────────────────────


@clinician_router.get(
    "/adherence-heatmap", response_model=AdherenceHeatmapResponse
)
async def adherence_heatmap(
    clinician: Clinician = Depends(verify_clinician),
    session: AsyncSession = Depends(get_db_session),
):
    cells = await get_adherence_heatmap_data(session)
    return AdherenceHeatmapResponse(
        cells=[AdherenceHeatmapCell(**c) for c in cells]
    )


@clinician_router.get(
    "/outcome-trends", response_model=OutcomeTrendsResponse
)
async def outcome_trends(
    clinician: Clinician = Depends(verify_clinician),
    session: AsyncSession = Depends(get_db_session),
):
    trends = await get_all_outcome_trends(session)
    return OutcomeTrendsResponse(
        trends=[PatientOutcomeTrend(**t) for t in trends]
    )


# ── AI-Powered Endpoints ────────────────────────────────────────────────────


@clinician_router.get(
    "/patients/{patient_id}/ai-summary",
    response_model=PatientAISummaryResponse,
)
async def patient_ai_summary(
    patient_id: str,
    clinician: Clinician = Depends(verify_clinician),
    session: AsyncSession = Depends(get_db_session),
):
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    from app.services.clinician_ai import generate_patient_summary

    result = await generate_patient_summary(session, patient_id)
    return PatientAISummaryResponse(
        patient_id=patient_id,
        date=datetime.date.today().isoformat(),
        summary=result["summary"],
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        risk_explanation=result["risk_explanation"],
        risk_factors=result["risk_factors"],
        is_cached=result["is_cached"],
    )


@clinician_router.get(
    "/caseload-briefing",
    response_model=CaseloadBriefingResponse,
)
async def caseload_briefing(
    clinician: Clinician = Depends(verify_clinician),
    session: AsyncSession = Depends(get_db_session),
):
    from app.services.clinician_ai import generate_caseload_briefing

    result = await generate_caseload_briefing(session, clinician.clinician_id)
    return CaseloadBriefingResponse(
        clinician_id=clinician.clinician_id,
        date=datetime.date.today().isoformat(),
        briefing=result["briefing"],
        patient_count=result["patient_count"],
        high_risk_count=result["high_risk_count"],
        is_cached=result["is_cached"],
    )
