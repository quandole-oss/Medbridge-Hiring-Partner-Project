import logging

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from app.graph.prompts import ACTIVE_COACHING_SYSTEM_PROMPT
from app.graph.state import GraphState
from app.graph.tools import get_adherence_summary, get_education_recommendation, get_patient_insights, set_goal, set_reminder
from app.services.llm import get_conversation_llm

logger = logging.getLogger(__name__)

TONE_DESCRIPTIONS = {
    "celebration": "Celebrate their progress enthusiastically. Highlight achievements.",
    "nudge": "Gently encourage them to stay on track. Be supportive, not pushy.",
    "check-in": "Ask how they're doing. Show genuine interest in their wellbeing.",
    "general": "Be warm, supportive, and responsive to whatever they need.",
}

TOOL_MAP = {
    "set_goal": set_goal,
    "set_reminder": set_reminder,
    "get_adherence_summary": get_adherence_summary,
    "get_education_recommendation": get_education_recommendation,
}

MAX_TOOL_ITERATIONS = 3


def _clean_tool_orphans(messages):
    """Strip orphaned AIMessage tool_use blocks from message history.

    Needed to recover from already-corrupted InMemorySaver state where
    tool_use AIMessages were added without corresponding ToolMessages.
    """
    tool_result_ids = set()
    for m in messages:
        if isinstance(m, ToolMessage):
            tool_result_ids.add(m.tool_call_id)

    cleaned = []
    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, 'tool_calls', None):
            if all(tc["id"] in tool_result_ids for tc in msg.tool_calls):
                cleaned.append(msg)
            else:
                # Extract any text content, drop tool_use blocks
                if isinstance(msg.content, str) and msg.content:
                    cleaned.append(AIMessage(content=msg.content))
                elif isinstance(msg.content, list):
                    text_parts = [b.get("text", "") for b in msg.content
                                  if isinstance(b, dict) and b.get("type") == "text"]
                    if text_parts:
                        cleaned.append(AIMessage(content=" ".join(text_parts)))
        else:
            cleaned.append(msg)
    return cleaned


def active_coaching_node(state: GraphState) -> dict:
    """Active coaching conversation with tone injection and tool execution."""
    patient_id = state["patient_id"]
    current_goal = state.get("current_goal") or "No specific goal set yet"
    tone = state.get("tone_instruction") or "general"

    adherence = get_adherence_summary.invoke({"patient_id": patient_id})
    insights = get_patient_insights.invoke({"patient_id": patient_id})

    system_prompt = ACTIVE_COACHING_SYSTEM_PROMPT.format(
        current_goal=current_goal,
        adherence_summary=adherence,
        tone_instruction=TONE_DESCRIPTIONS.get(tone, TONE_DESCRIPTIONS["general"]),
        patient_insights=insights,
    )

    llm = get_conversation_llm().bind_tools([set_goal, set_reminder, get_adherence_summary, get_education_recommendation])

    # Sanitize messages: strip orphaned tool_use AIMessages from prior corrupted state
    clean_msgs = _clean_tool_orphans(list(state["messages"]))

    messages = [SystemMessage(content=system_prompt)] + clean_msgs
    response = llm.invoke(messages)

    all_new_messages = []
    iteration = 0
    while getattr(response, 'tool_calls', None) and iteration < MAX_TOOL_ITERATIONS:
        all_new_messages.append(response)
        for tc in response.tool_calls:
            tool_fn = TOOL_MAP.get(tc["name"])
            result = tool_fn.invoke(tc["args"]) if tool_fn else f"Unknown tool: {tc['name']}"
            all_new_messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
        response = llm.invoke(messages + all_new_messages)
        iteration += 1

    all_new_messages.append(response)
    return {"messages": all_new_messages}
