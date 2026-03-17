import logging
from typing import Optional

from langchain_core.messages import AIMessage, SystemMessage
from pydantic import BaseModel, Field

from app.graph.prompts import ONBOARDING_SYSTEM_PROMPT
from app.graph.state import GraphState, Phase
from app.graph.tools import get_patient_insights, get_program_summary, set_goal
from app.services.llm import get_conversation_llm

logger = logging.getLogger(__name__)


class GoalExtraction(BaseModel):
    goal_text: Optional[str] = Field(
        description="The SMART goal extracted from the conversation, or None if no goal was set"
    )
    target_date: Optional[str] = Field(
        None,
        description="Target date for the goal in ISO format (YYYY-MM-DD), if mentioned"
    )
    is_refusal: bool = Field(
        description="Whether the patient declined to set a goal"
    )


def onboarding_node(state: GraphState) -> dict:
    """Guide patient through onboarding and goal-setting."""
    patient_id = state["patient_id"]
    program_summary = get_program_summary.invoke({"patient_id": patient_id})
    insights = get_patient_insights.invoke({"patient_id": patient_id})

    system_prompt = ONBOARDING_SYSTEM_PROMPT.format(
        program_summary=program_summary,
        patient_insights=insights,
    )

    llm = get_conversation_llm()
    response = llm.invoke(
        [SystemMessage(content=system_prompt)] + list(state["messages"])
    )

    return {"messages": [response]}


def check_goal_extraction(state: GraphState) -> dict:
    """After sufficient conversation, attempt to extract a goal."""
    messages = state["messages"]
    # Only attempt extraction after at least 2 exchanges (4 messages: user+ai pairs)
    user_messages = [m for m in messages if not isinstance(m, (AIMessage, SystemMessage))]
    if len(user_messages) < 2:
        return {}

    llm = get_conversation_llm().with_structured_output(GoalExtraction)
    extraction = llm.invoke(
        [SystemMessage(content=(
            "Analyze the conversation and extract any SMART goal the patient has agreed to. "
            "If they explicitly declined to set a goal, mark is_refusal=True. "
            "If the conversation hasn't reached a clear goal or refusal yet, "
            "set goal_text=None and is_refusal=False."
        ))] + list(messages)
    )

    if extraction.goal_text:
        invoke_args = {
            "patient_id": state["patient_id"],
            "goal_text": extraction.goal_text,
        }
        if extraction.target_date:
            invoke_args["target_date"] = extraction.target_date
        set_goal.invoke(invoke_args)
        logger.info("Goal extracted for %s: %s", state["patient_id"], extraction.goal_text)
        return {
            "current_phase": Phase.ACTIVE,
            "current_goal": extraction.goal_text,
        }
    elif extraction.is_refusal:
        logger.info("Patient %s declined to set goal", state["patient_id"])
        return {
            "current_phase": Phase.ACTIVE,
            "current_goal": None,
        }

    return {}
