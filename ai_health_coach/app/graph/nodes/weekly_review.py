"""Weekly review graph node — structured data-driven check-in with MI techniques."""
import logging

from langchain_core.messages import AIMessage, SystemMessage

from app.graph.prompts import MI_TECHNIQUES_SECTION, WEEKLY_REVIEW_SYSTEM_PROMPT
from app.graph.state import GraphState
from app.graph.tools import get_adherence_summary, get_patient_insights
from app.services.llm import FALLBACK_MESSAGE, get_conversation_llm

logger = logging.getLogger(__name__)


def weekly_review_node(state: GraphState) -> dict:
    """Structured weekly review with MI techniques for declining adherence."""
    patient_id = state["patient_id"]
    current_goal = state.get("current_goal") or "No specific goal set yet"

    # Gather data
    adherence_text = get_adherence_summary.invoke({"patient_id": patient_id})
    insights_text = get_patient_insights.invoke({"patient_id": patient_id})

    # Parse adherence rate to decide MI section
    mi_section = ""
    try:
        # adherence_text contains completion_rate info
        if "completion_rate" in adherence_text:
            # Extract rate from the text
            import re
            rate_match = re.search(r"completion_rate['\"]?\s*[:=]\s*([\d.]+)", adherence_text)
            if rate_match:
                rate = float(rate_match.group(1))
                if rate < 60:
                    mi_section = MI_TECHNIQUES_SECTION
    except Exception:
        pass

    patient_data = (
        "Goals: {goals}\n"
        "Adherence: {adherence}\n"
        "Patient insights: {insights}"
    ).format(
        goals=current_goal,
        adherence=adherence_text,
        insights=insights_text,
    )

    system_prompt = WEEKLY_REVIEW_SYSTEM_PROMPT.format(
        patient_data=patient_data,
        mi_section=mi_section,
    )

    llm = get_conversation_llm()
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
        ])
    except Exception:
        logger.exception("Weekly review generation failed for %s", patient_id)
        response = AIMessage(content=FALLBACK_MESSAGE)

    return {
        "messages": [response],
        "_weekly_review": False,
    }
