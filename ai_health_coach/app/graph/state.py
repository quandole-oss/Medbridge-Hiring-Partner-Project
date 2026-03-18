from enum import Enum
from typing import Annotated, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class Phase(str, Enum):
    PENDING = "pending"
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    RE_ENGAGING = "re_engaging"
    DORMANT = "dormant"


class GraphState(TypedDict):
    patient_id: str
    current_phase: Phase
    messages: Annotated[List[BaseMessage], add_messages]
    unanswered_count: int
    current_goal: Optional[str]
    tone_instruction: Optional[str]
    safety_retry_count: int
    enrollment_date: str
    _safety_verdict: Optional[str]
    _weekly_review: Optional[bool]
