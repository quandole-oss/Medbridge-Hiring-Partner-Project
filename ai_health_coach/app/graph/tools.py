from langchain_core.tools import tool
from pydantic import BaseModel, Field


class SetGoalInput(BaseModel):
    patient_id: str = Field(description="The patient's unique identifier")
    goal_text: str = Field(description="The SMART goal text")


class SetReminderInput(BaseModel):
    patient_id: str = Field(description="The patient's unique identifier")
    reminder_text: str = Field(description="What to remind the patient about")
    time: str = Field(description="When to send the reminder (ISO format or natural language)")


class AlertClinicianInput(BaseModel):
    patient_id: str = Field(description="The patient's unique identifier")
    reason: str = Field(description="Why the clinician is being alerted")
    urgency_level: str = Field(description="CRITICAL, HIGH, or LOW")


@tool(args_schema=SetGoalInput)
def set_goal(patient_id: str, goal_text: str) -> str:
    """Persist a SMART goal for the patient. Use when the patient has articulated a clear goal."""
    return f"Goal set for patient {patient_id}: {goal_text}"


@tool(args_schema=SetReminderInput)
def set_reminder(patient_id: str, reminder_text: str, time: str) -> str:
    """Create a reminder for the patient. Use when the patient wants to be reminded about exercises or appointments."""
    return f"Reminder set for patient {patient_id}: '{reminder_text}' at {time}"


@tool
def get_program_summary(patient_id: str) -> str:
    """Get a summary of the patient's physical therapy program."""
    return (
        "Your program includes personalized exercises designed by your physical therapist, "
        "progress tracking, and regular check-ins. Exercises are updated based on your "
        "recovery progress and feedback. You can do them at home at your own pace."
    )


@tool
def get_adherence_summary(patient_id: str) -> str:
    """Get the patient's exercise adherence summary."""
    return (
        "Completed 8 of 12 assigned exercises this week. "
        "Consistency is good on upper body exercises. "
        "Lower body exercises have been less frequent."
    )


@tool(args_schema=AlertClinicianInput)
def alert_clinician(patient_id: str, reason: str, urgency_level: str) -> str:
    """Alert the patient's clinician. Use for crisis situations or when clinical intervention is needed."""
    return f"ALERT sent to clinician for patient {patient_id}: [{urgency_level}] {reason}"
