"""Clinician AI services — patient summaries, risk explanations, caseload briefings."""
import asyncio
import datetime
import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import (
    count_open_alerts,
    get_active_goals,
    get_adherence_stats,
    get_alerts,
    get_all_patients,
    get_caseload_briefing_cached,
    get_difficulty_pattern_summary,
    get_outcome_summary,
    get_patient,
    get_patient_insights_db,
    get_patient_summary_cached,
    save_caseload_briefing,
    save_patient_summary,
)
from app.graph.prompts import (
    CASELOAD_BRIEFING_PROMPT,
    CLINICIAN_PATIENT_SUMMARY_PROMPT,
    RISK_EXPLANATION_PROMPT,
)
from app.services.llm import get_safety_llm
from app.services.risk_scoring import compute_risk_score

logger = logging.getLogger(__name__)


async def generate_patient_summary(
    session: AsyncSession, patient_id: str
) -> dict:
    """Generate AI summary + risk score for a patient. Cached per day.

    Returns dict with keys: summary, risk_score, risk_level,
    risk_explanation, risk_factors, is_cached
    """
    today = datetime.date.today()

    # Check cache
    cached = await get_patient_summary_cached(session, patient_id, today)
    if cached:
        return {
            "summary": cached.summary_text,
            "risk_score": cached.risk_score,
            "risk_level": cached.risk_level,
            "risk_explanation": cached.risk_explanation,
            "risk_factors": cached.risk_factors or {},
            "is_cached": True,
        }

    patient = await get_patient(session, patient_id)
    if not patient:
        return {
            "summary": "Patient not found.",
            "risk_score": 0,
            "risk_level": "low",
            "risk_explanation": "No data available.",
            "risk_factors": {},
            "is_cached": False,
        }

    # Gather all data in one pass
    adherence = await get_adherence_stats(session, patient_id)
    outcomes = await get_outcome_summary(session, patient_id)
    goals = await get_active_goals(session, patient_id)
    insights = await get_patient_insights_db(session, patient_id, limit=5)
    difficulty = await get_difficulty_pattern_summary(session, patient_id)
    alerts = await get_alerts(session, status="open", patient_id=patient_id)

    # Compute days since last message
    days_since = None
    if patient.last_message_at:
        now = datetime.datetime.now(datetime.timezone.utc)
        lm = patient.last_message_at
        if lm.tzinfo is None:
            lm = lm.replace(tzinfo=datetime.timezone.utc)
        days_since = (now - lm).days

    # Alert counts for risk scoring
    alert_counts = {"critical": 0, "high": 0, "low": 0}
    for a in alerts:
        urgency = a.urgency.lower() if a.urgency else "low"
        if urgency in alert_counts:
            alert_counts[urgency] += 1

    # Compute risk score (pure heuristic)
    risk = compute_risk_score(
        adherence=adherence,
        outcomes=outcomes,
        difficulty=difficulty,
        phase=patient.current_phase or "active",
        days_since_last_message=days_since,
        open_alert_counts=alert_counts,
    )

    # Build context for LLM
    goal_text = ", ".join(g.goal_text for g in goals) if goals else "None set"
    insight_text = "; ".join(i.content for i in insights) if insights else "None"

    context = (
        "Patient: {pid}\n"
        "Phase: {phase} | Day {day} of program | Streak: {streak} days\n"
        "Adherence: {completed}/{due} exercises ({rate}% completion)\n"
        "Pain: {pain}/10 ({pain_trend}) | Function: {func}/10 ({func_trend}) | "
        "Wellbeing: {well}/10 ({well_trend})\n"
        "Difficulty pattern: {hard} too_hard, {easy} too_easy, {right} just_right\n"
        "Goals: {goals}\n"
        "Open alerts: {alert_count} ({alert_detail})\n"
        "Days since last message: {days_since}\n"
        "Patient insights: {insights}"
    ).format(
        pid=patient_id,
        phase=patient.current_phase or "unknown",
        day=adherence.get("days_in_program", 1),
        streak=adherence.get("streak", 0),
        completed=adherence.get("total_completed", 0),
        due=adherence.get("total_due", 0),
        rate=adherence.get("completion_rate", 0),
        pain=outcomes.get("latest", {}).get("pain_score", "N/A") if outcomes.get("latest") else "N/A",
        pain_trend=outcomes.get("pain_trend", "stable"),
        func=outcomes.get("latest", {}).get("function_score", "N/A") if outcomes.get("latest") else "N/A",
        func_trend=outcomes.get("function_trend", "stable"),
        well=outcomes.get("latest", {}).get("wellbeing_score", "N/A") if outcomes.get("latest") else "N/A",
        well_trend=outcomes.get("wellbeing_trend", "stable"),
        hard=difficulty.get("too_hard", 0),
        easy=difficulty.get("too_easy", 0),
        right=difficulty.get("just_right", 0),
        goals=goal_text,
        alert_count=len(alerts),
        alert_detail=", ".join("{} {}".format(a.urgency, a.alert_type) for a in alerts) or "none",
        days_since=days_since if days_since is not None else "N/A",
        insights=insight_text,
    )

    # Risk factor context for explanation
    risk_context = "Risk score: {score}/100 ({level})\nTop factors: {factors}".format(
        score=risk["score"],
        level=risk["level"],
        factors=", ".join(
            "{} (+{})".format(k, v)
            for k, v in sorted(risk["factors"].items(), key=lambda x: -x[1])
            if v > 0
        ),
    )

    # Generate summary and risk explanation in parallel
    llm = get_safety_llm()
    try:
        summary_task = llm.ainvoke([
            SystemMessage(content=CLINICIAN_PATIENT_SUMMARY_PROMPT),
            HumanMessage(content=context),
        ])
        explanation_task = llm.ainvoke([
            SystemMessage(content=RISK_EXPLANATION_PROMPT.format(
                score=risk["score"], level=risk["level"]
            )),
            HumanMessage(content=context + "\n\n" + risk_context),
        ])
        summary_resp, explanation_resp = await asyncio.gather(
            summary_task, explanation_task
        )
        summary_text = summary_resp.content if isinstance(summary_resp.content, str) else str(summary_resp.content)
        risk_explanation = explanation_resp.content if isinstance(explanation_resp.content, str) else str(explanation_resp.content)
    except Exception:
        logger.exception("AI summary generation failed for %s", patient_id)
        summary_text = (
            "Day {} of program. {}% adherence rate, {}-day streak. "
            "Pain trend: {}. {} open alerts.".format(
                adherence.get("days_in_program", 1),
                adherence.get("completion_rate", 0),
                adherence.get("streak", 0),
                outcomes.get("pain_trend", "stable"),
                len(alerts),
            )
        )
        risk_explanation = "Risk score: {}/100. Review patient data for details.".format(
            risk["score"]
        )

    # Cache
    await save_patient_summary(
        session, patient_id, today,
        summary_text=summary_text,
        risk_score=risk["score"],
        risk_level=risk["level"],
        risk_explanation=risk_explanation,
        risk_factors=risk["factors"],
    )

    return {
        "summary": summary_text,
        "risk_score": risk["score"],
        "risk_level": risk["level"],
        "risk_explanation": risk_explanation,
        "risk_factors": risk["factors"],
        "is_cached": False,
    }


async def generate_caseload_briefing(
    session: AsyncSession, clinician_id: str
) -> dict:
    """Generate daily caseload briefing across all patients. Cached per day.

    Returns dict with keys: briefing, patient_count, high_risk_count, is_cached
    """
    today = datetime.date.today()

    # Check cache
    cached = await get_caseload_briefing_cached(session, clinician_id, today)
    if cached:
        return {
            "briefing": cached.briefing_text,
            "patient_count": cached.patient_count,
            "high_risk_count": cached.high_risk_count,
            "is_cached": True,
        }

    patients = await get_all_patients(session)
    if not patients:
        return {
            "briefing": "No patients in the system.",
            "patient_count": 0,
            "high_risk_count": 0,
            "is_cached": False,
        }

    # Generate summaries for all patients (cached ones return instantly)
    summaries = []
    for p in patients:
        s = await generate_patient_summary(session, p.patient_id)
        summaries.append({"patient_id": p.patient_id, **s})

    # Sort by risk score descending
    summaries.sort(key=lambda x: x["risk_score"], reverse=True)

    high_risk_count = sum(
        1 for s in summaries if s["risk_level"] in ("high", "critical")
    )

    # Build context for caseload briefing
    patient_lines = []
    for s in summaries:
        patient_lines.append(
            "- {pid}: Risk {score}/100 ({level}). {summary}".format(
                pid=s["patient_id"],
                score=s["risk_score"],
                level=s["risk_level"],
                summary=s["summary"],
            )
        )

    context = "Today's date: {}\n\nPatient summaries:\n{}".format(
        today.isoformat(),
        "\n".join(patient_lines),
    )

    llm = get_safety_llm()
    try:
        response = await llm.ainvoke([
            SystemMessage(content=CASELOAD_BRIEFING_PROMPT.format(
                patient_count=len(patients),
            )),
            HumanMessage(content=context),
        ])
        briefing_text = response.content if isinstance(response.content, str) else str(response.content)
    except Exception:
        logger.exception("Caseload briefing generation failed")
        briefing_text = (
            "Caseload: {} patients, {} at high/critical risk. "
            "Review individual patient summaries for details.".format(
                len(patients), high_risk_count
            )
        )

    # Cache
    await save_caseload_briefing(
        session, clinician_id, today,
        briefing_text=briefing_text,
        patient_count=len(patients),
        high_risk_count=high_risk_count,
    )

    return {
        "briefing": briefing_text,
        "patient_count": len(patients),
        "high_risk_count": high_risk_count,
        "is_cached": False,
    }
