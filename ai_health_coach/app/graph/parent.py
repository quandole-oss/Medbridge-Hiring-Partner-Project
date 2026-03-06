import logging

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graph.nodes.active import active_coaching_node
from app.graph.nodes.onboarding import check_goal_extraction, onboarding_node
from app.graph.nodes.re_engaging import re_engaging_node
from app.graph.nodes.safety import (
    crisis_handler_node,
    route_after_safety,
    safety_check_node,
    safety_fallback_node,
)
from app.graph.state import GraphState, Phase
from app.services.llm import FALLBACK_MESSAGE, get_conversation_llm

logger = logging.getLogger(__name__)

PHASE_ROUTES = {
    Phase.ONBOARDING: "onboarding_node",
    Phase.ACTIVE: "active_coaching_node",
    Phase.RE_ENGAGING: "re_engaging_node",
    Phase.DORMANT: "dormant_handler",
}


def route_by_phase(state: GraphState) -> str:
    """Pure dictionary lookup router. No LLM calls."""
    phase = state["current_phase"]
    route = PHASE_ROUTES.get(phase)
    if route is None:
        raise ValueError(
            f"Undefined phase route: {phase}. "
            f"Legal phases: {list(PHASE_ROUTES.keys())}"
        )
    return route


def dormant_handler(state: GraphState) -> dict:
    """Static response for dormant patients (shouldn't normally be reached)."""
    return {
        "messages": [
            AIMessage(
                content="We're here whenever you're ready to continue your program. "
                "Just send a message anytime."
            )
        ]
    }


def retry_node(state: GraphState) -> dict:
    """Re-invoke the LLM with augmented safety instructions."""
    llm = get_conversation_llm()
    from langchain_core.messages import SystemMessage

    safety_augment = SystemMessage(content=(
        "CRITICAL: Your previous response was flagged as unsafe. "
        "You MUST NOT give specific medical advice, medication recommendations, "
        "dosage suggestions, or discuss topics outside physical therapy and wellness. "
        "Redirect clinical questions to the patient's physical therapist. "
        "Stay focused on encouragement, goal-setting, and program support."
    ))

    # Re-invoke with safety augmentation, excluding the last flagged AI message
    messages = list(state["messages"])
    # Remove the last AI message (the flagged one)
    clean_messages = []
    removed = False
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not removed:
            removed = True
            continue
        clean_messages.append(msg)
    clean_messages.reverse()

    response = llm.invoke([safety_augment] + clean_messages)
    return {
        "messages": [response],
        "safety_retry_count": state.get("safety_retry_count", 0) + 1,
    }


def build_graph() -> StateGraph:
    """Build and compile the parent graph with all subgraph nodes."""
    graph = StateGraph(GraphState)

    # Phase subgraph nodes
    graph.add_node("onboarding_node", onboarding_node)
    graph.add_node("active_coaching_node", active_coaching_node)
    graph.add_node("re_engaging_node", re_engaging_node)
    graph.add_node("dormant_handler", dormant_handler)

    # Safety pipeline nodes
    graph.add_node("safety_check", safety_check_node)
    graph.add_node("retry_node", retry_node)
    graph.add_node("crisis_handler", crisis_handler_node)
    graph.add_node("safety_fallback", safety_fallback_node)

    # Onboarding post-processing
    graph.add_node("check_goal_extraction", check_goal_extraction)

    # START -> phase router
    graph.add_conditional_edges(START, route_by_phase, PHASE_ROUTES)

    # Each subgraph -> safety_check
    graph.add_edge("onboarding_node", "safety_check")
    graph.add_edge("active_coaching_node", "safety_check")
    graph.add_edge("re_engaging_node", "safety_check")
    graph.add_edge("dormant_handler", END)

    # Safety check -> conditional routing
    graph.add_conditional_edges(
        "safety_check",
        route_after_safety,
        {
            "safe": "check_goal_extraction",
            "retry": "retry_node",
            "crisis": "crisis_handler",
            "fallback": "safety_fallback",
        },
    )

    # Retry -> safety_check (re-evaluate)
    graph.add_edge("retry_node", "safety_check")

    # Terminal nodes
    graph.add_edge("crisis_handler", END)
    graph.add_edge("safety_fallback", END)
    graph.add_edge("check_goal_extraction", END)

    return graph


# Module-level compiled graph with InMemorySaver
checkpointer = MemorySaver()
compiled_graph = build_graph().compile(checkpointer=checkpointer)
