import logging

from langchain_core.messages import AIMessage, SystemMessage

from app.graph.prompts import RE_ENGAGING_SYSTEM_PROMPT
from app.graph.state import GraphState, Phase
from app.graph.tools import get_patient_insights
from app.services.llm import get_conversation_llm

logger = logging.getLogger(__name__)


def re_engaging_node(state: GraphState) -> dict:
    """Welcome back a patient from dormancy without guilt."""
    patient_id = state["patient_id"]
    insights = get_patient_insights.invoke({"patient_id": patient_id})

    system_prompt = RE_ENGAGING_SYSTEM_PROMPT.format(patient_insights=insights)

    llm = get_conversation_llm()
    response = llm.invoke(
        [SystemMessage(content=system_prompt)] + list(state["messages"])
    )

    logger.info("Re-engaging patient %s", state["patient_id"])
    return {
        "messages": [response],
        "current_phase": Phase.ACTIVE,
        "unanswered_count": 0,
    }
