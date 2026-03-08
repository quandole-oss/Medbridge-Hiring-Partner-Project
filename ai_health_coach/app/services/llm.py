import logging
from typing import List, Optional

from anthropic import APIError, RateLimitError
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = (
    "I'm having a little trouble right now. "
    "Please try again in a moment, or reach out to your care team directly."
)


def get_conversation_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.CONVERSATION_MODEL,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=1024,
        max_retries=3,
    )


def get_safety_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.SAFETY_MODEL,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=256,
        max_retries=3,
    )


class ExerciseAdjustment(BaseModel):
    name: str = Field(description="Name of the replacement exercise")
    description: str = Field(description="Clear instructions for the patient")
    body_part: str = Field(description="Primary body part targeted")
    sets: int = Field(description="Number of sets")
    reps: int = Field(description="Number of reps per set")
    hold_seconds: Optional[int] = Field(
        None, description="Hold duration in seconds, if applicable"
    )
    reasoning: str = Field(
        description="Brief explanation of why this replacement was chosen"
    )


async def get_exercise_adjustment(
    exercise,
    difficulty: str,
    feedback: Optional[str] = None,
    set_statuses: Optional[List[Optional[str]]] = None,
) -> dict:
    system_prompt = (
        "You are a physical therapist program designer. A patient has reported "
        "difficulty feedback on an exercise in their home exercise program. "
        "Based on the difficulty level and their feedback, suggest a replacement exercise.\n\n"
        "Rules:\n"
        "- If 'too_hard': suggest an easier variation targeting the same body part. "
        "Reduce sets, reps, or hold time. Consider simpler movements.\n"
        "- If 'too_easy': suggest a harder progression. Increase sets, reps, hold time, "
        "or suggest a more challenging movement for the same body part.\n"
        "- Keep the exercise appropriate for a post-operative rehabilitation patient.\n"
        "- The description should be clear, concise instructions a patient can follow at home.\n"
        "- Keep the same body_part category as the original exercise."
    )

    exercise_info = (
        f"Current exercise: {exercise.name}\n"
        f"Description: {exercise.description}\n"
        f"Body part: {exercise.body_part}\n"
        f"Sets: {exercise.sets}, Reps: {exercise.reps}"
    )
    if exercise.hold_seconds:
        exercise_info += f", Hold: {exercise.hold_seconds}s"

    exercise_info += f"\n\nPatient reports this exercise is: {difficulty}"
    if set_statuses:
        total = len(set_statuses)
        attempted = sum(1 for s in set_statuses if s is not None)
        complete_count = sum(1 for s in set_statuses if s == "complete")
        partial_count = sum(1 for s in set_statuses if s == "partial")
        labels = [s if s else "unchecked" for s in set_statuses]
        exercise_info += (
            f"\nSet completion detail: {total} sets - [{', '.join(labels)}] "
            f"({attempted} attempted: {complete_count} fully complete, {partial_count} partial)"
        )
    if feedback:
        exercise_info += f"\nPatient feedback: {feedback}"

    llm = get_conversation_llm().with_structured_output(ExerciseAdjustment)

    try:
        result = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=exercise_info),
        ])
        return result.dict()
    except Exception:
        logger.exception("Exercise adjustment LLM call failed")
        if difficulty == "too_hard":
            return {
                "name": f"Modified {exercise.name}",
                "description": f"Easier version: {exercise.description} Do fewer reps and take breaks as needed.",
                "body_part": exercise.body_part,
                "sets": max(1, exercise.sets - 1),
                "reps": max(1, exercise.reps // 2),
                "hold_seconds": (
                    max(5, exercise.hold_seconds // 2) if exercise.hold_seconds else None
                ),
                "reasoning": "Reduced intensity as a simpler alternative. Please discuss with your care team for personalized adjustments.",
            }
        else:
            return {
                "name": f"Advanced {exercise.name}",
                "description": f"Harder version: {exercise.description} Increase the challenge gradually.",
                "body_part": exercise.body_part,
                "sets": exercise.sets + 1,
                "reps": exercise.reps + 5,
                "hold_seconds": (
                    exercise.hold_seconds + 10 if exercise.hold_seconds else None
                ),
                "reasoning": "Increased intensity for progression. Please discuss with your care team for personalized adjustments.",
            }
