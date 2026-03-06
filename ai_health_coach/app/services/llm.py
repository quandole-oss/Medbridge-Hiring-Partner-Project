import logging

from anthropic import APIError, RateLimitError
from langchain_anthropic import ChatAnthropic

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
