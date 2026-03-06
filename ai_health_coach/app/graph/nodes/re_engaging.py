import logging

from langchain_core.messages import AIMessage, SystemMessage

from app.graph.prompts import RE_ENGAGING_SYSTEM_PROMPT
from app.graph.state import GraphState, Phase
from app.services.llm import get_conversation_llm

logger = logging.getLogger(__name__)


def re_engaging_node(state: GraphState) -> dict:
    """Welcome back a patient from dormancy without guilt."""
    llm = get_conversation_llm()
    response = llm.invoke(
        [SystemMessage(content=RE_ENGAGING_SYSTEM_PROMPT)] + list(state["messages"])
    )

    logger.info("Re-engaging patient %s", state["patient_id"])
    return {
        "messages": [response],
        "current_phase": Phase.ACTIVE,
        "unanswered_count": 0,
    }
