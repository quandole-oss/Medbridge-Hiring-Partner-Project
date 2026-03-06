import logging

from langchain_core.messages import SystemMessage

from app.db.repository import get_disengaged_patients, log_audit_event, update_patient_phase
from app.db.session import async_session_factory
from app.graph.parent import compiled_graph
from app.graph.state import Phase
from app.graph.tools import alert_clinician

logger = logging.getLogger(__name__)

# Backoff: attempt 1 at 24h, attempt 2 at 48h, attempt 3 at 72h
BACKOFF_HOURS = [24, 48, 72]


async def run_disengagement_check() -> int:
    """Check for disengaged patients and send outreach via graph invocation.

    Returns the number of patients contacted.
    """
    contacted = 0

    async with async_session_factory() as session:
        for attempt_index, hours in enumerate(BACKOFF_HOURS):
            patients = await get_disengaged_patients(session, hours)

            for patient in patients:
                if patient.unanswered_count != attempt_index:
                    continue

                logger.info(
                    "Disengagement check: patient %s, attempt %d",
                    patient.patient_id,
                    attempt_index + 1,
                )

                try:
                    result = await compiled_graph.ainvoke(
                        {
                            "patient_id": patient.patient_id,
                            "current_phase": Phase.ACTIVE,
                            "messages": [
                                SystemMessage(
                                    content="[DISENGAGEMENT_CHECK] Generate a brief, "
                                    "warm outreach message encouraging the patient to "
                                    "continue their exercises. Do not be pushy."
                                )
                            ],
                            "unanswered_count": patient.unanswered_count + 1,
                            "current_goal": None,
                            "tone_instruction": "nudge",
                            "safety_retry_count": 0,
                            "enrollment_date": (
                                patient.enrollment_date.isoformat()
                                if patient.enrollment_date
                                else ""
                            ),
                        },
                        config={
                            "configurable": {
                                "thread_id": patient.patient_id
                            }
                        },
                    )

                    new_count = result.get("unanswered_count", patient.unanswered_count + 1)

                    # Update DB
                    patient.unanswered_count = new_count
                    await session.commit()

                    if new_count >= 3:
                        alert_clinician.invoke({
                            "patient_id": patient.patient_id,
                            "reason": "Patient unresponsive after 3 outreach attempts",
                            "urgency_level": "LOW",
                        })
                        await update_patient_phase(
                            session, patient.patient_id, Phase.DORMANT
                        )
                        await log_audit_event(
                            session,
                            patient.patient_id,
                            "dormancy_transition",
                            {"unanswered_count": new_count},
                        )
                        logger.warning(
                            "Patient %s moved to DORMANT", patient.patient_id
                        )

                    contacted += 1

                except Exception:
                    logger.exception(
                        "Disengagement check failed for patient %s",
                        patient.patient_id,
                    )

    return contacted
