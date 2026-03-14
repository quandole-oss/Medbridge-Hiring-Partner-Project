import logging

from langchain_core.messages import AIMessage, SystemMessage

from app.graph.prompts import ACTIVE_COACHING_SYSTEM_PROMPT
from app.graph.state import GraphState
from app.graph.tools import get_adherence_summary, get_education_recommendation, set_reminder
from app.services.llm import get_conversation_llm

logger = logging.getLogger(__name__)

TONE_DESCRIPTIONS = {
    "celebration": "Celebrate their progress enthusiastically. Highlight achievements.",
    "nudge": "Gently encourage them to stay on track. Be supportive, not pushy.",
    "check-in": "Ask how they're doing. Show genuine interest in their wellbeing.",
    "general": "Be warm, supportive, and responsive to whatever they need.",
}


def active_coaching_node(state: GraphState) -> dict:
    """Active coaching conversation with tone injection."""
    patient_id = state["patient_id"]
    current_goal = state.get("current_goal") or "No specific goal set yet"
    tone = state.get("tone_instruction") or "general"

    adherence = get_adherence_summary.invoke({"patient_id": patient_id})

    system_prompt = ACTIVE_COACHING_SYSTEM_PROMPT.format(
        current_goal=current_goal,
        adherence_summary=adherence,
        tone_instruction=TONE_DESCRIPTIONS.get(tone, TONE_DESCRIPTIONS["general"]),
    )

    llm = get_conversation_llm().bind_tools([set_reminder, get_adherence_summary, get_education_recommendation])
    response = llm.invoke(
        [SystemMessage(content=system_prompt)] + list(state["messages"])
    )

    return {"messages": [response]}
