import datetime
import logging
import time
from collections import OrderedDict
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import verify_api_key, verify_consent
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    EventTriggerRequest,
    EventTriggerResponse,
    HealthResponse,
    PatientStatusResponse,
)
from app.db.repository import (
    get_active_goal,
    get_patient,
    grant_consent,
    log_audit_event,
    update_patient_last_message,
    update_patient_phase,
)
from app.db.session import get_db_session
from app.graph.parent import compiled_graph
from app.graph.state import Phase
from app.services.llm import FALLBACK_MESSAGE

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
    days = (datetime.datetime.now(datetime.timezone.utc) - enrollment_date).days
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
    )
