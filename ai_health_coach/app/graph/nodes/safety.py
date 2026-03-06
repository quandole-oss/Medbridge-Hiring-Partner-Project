import logging
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from pydantic import BaseModel, Field

from app.graph.prompts import CRISIS_RESPONSE, SAFETY_CLASSIFIER_PROMPT, SAFETY_FALLBACK_RESPONSE
from app.graph.state import GraphState
from app.graph.tools import alert_clinician
from app.services.llm import get_safety_llm

logger = logging.getLogger(__name__)


class SafetyVerdict(BaseModel):
    is_safe: bool = Field(description="Whether the response is safe to deliver")
    violation_type: Literal["safe", "clinical_advice", "crisis", "out_of_scope"] = Field(
        description="Type of safety violation detected"
    )
    explanation: str = Field(description="Brief explanation of the classification")


def get_safety_classifier():
    return get_safety_llm().with_structured_output(SafetyVerdict)


def safety_check_node(state: GraphState) -> dict:
    """Classify the last AI message for safety violations."""
    messages = state["messages"]
    last_ai_message = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            last_ai_message = msg
            break

    if not last_ai_message:
        return {"safety_retry_count": 0}

    classifier = get_safety_classifier()
    verdict = classifier.invoke([
        SystemMessage(content=SAFETY_CLASSIFIER_PROMPT),
        last_ai_message,
    ])

    logger.info(
        "Safety verdict: %s (%s)", verdict.violation_type, verdict.explanation
    )

    return {
        "_safety_verdict": verdict.violation_type,
        "safety_retry_count": state.get("safety_retry_count", 0),
    }


def route_after_safety(state: GraphState) -> str:
    """Route based on safety classification result."""
    verdict = state.get("_safety_verdict", "safe")
    if verdict == "safe":
        return "safe"
    if verdict == "crisis":
        return "crisis"
    # clinical_advice or out_of_scope
    if state.get("safety_retry_count", 0) < 1:
        return "retry"
    return "fallback"


def crisis_handler_node(state: GraphState) -> dict:
    """Handle crisis detection: alert clinician, return static response."""
    patient_id = state["patient_id"]
    alert_clinician.invoke({
        "patient_id": patient_id,
        "reason": "Crisis detected in conversation",
        "urgency_level": "CRITICAL",
    })
    logger.critical("CRISIS detected for patient %s", patient_id)
    return {
        "messages": [AIMessage(content=CRISIS_RESPONSE)],
        "safety_retry_count": 0,
    }


def safety_fallback_node(state: GraphState) -> dict:
    """Return hardcoded safe fallback after failed retry."""
    logger.warning("Safety retry exhausted for patient %s", state["patient_id"])
    return {
        "messages": [AIMessage(content=SAFETY_FALLBACK_RESPONSE)],
        "safety_retry_count": 0,
    }
