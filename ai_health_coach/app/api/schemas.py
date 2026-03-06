from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    patient_id: str
    message: str
    idempotency_key: Optional[str] = None


class ChatResponse(BaseModel):
    patient_id: str
    response: str
    current_phase: str
    current_goal: Optional[str] = None


class EventTriggerRequest(BaseModel):
    patient_id: str
    event_type: str = Field(
        description="One of: consent_granted, program_completed, manual_phase_override"
    )
    payload: Optional[dict] = None


class EventTriggerResponse(BaseModel):
    patient_id: str
    new_phase: str
    message: str


class PatientStatusResponse(BaseModel):
    patient_id: str
    current_phase: str
    current_goal: Optional[str]
    unanswered_count: int
    last_message_at: Optional[str]


class HealthResponse(BaseModel):
    status: str
