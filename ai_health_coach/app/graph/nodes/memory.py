import asyncio
import concurrent.futures
import logging
from typing import List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.graph.state import GraphState
from app.services.llm import get_safety_llm

logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = {
    "preference",
    "motivation",
    "barrier",
    "progress_note",
    "personal_context",
    "emotional_state",
}

EXTRACTION_PROMPT = """\
You are analyzing a physical therapy coaching conversation to extract structured \
insights about the patient. These will personalize future conversations.

Categories: preference, motivation, barrier, progress_note, personal_context, emotional_state

Rules:
- Only extract what the PATIENT revealed, not what the coach said
- Focus on durable facts, not transient states
- Under 20 words per insight, max 3 per conversation
- Do NOT extract medical diagnoses or clinical information
- Return empty list if nothing new is apparent"""


class ExtractedInsight(BaseModel):
    category: str
    content: str


class InsightExtractionResult(BaseModel):
    insights: List[ExtractedInsight] = Field(default_factory=list)


def extract_insights_node(state: GraphState) -> dict:
    """Extract patient insights from conversation and persist to DB."""
    messages = state.get("messages", [])
    patient_id = state["patient_id"]

    # Skip if no human messages
    has_human = any(isinstance(m, HumanMessage) for m in messages)
    if not has_human:
        return {}

    try:
        llm = get_safety_llm().with_structured_output(InsightExtractionResult)
        result = llm.invoke(
            [SystemMessage(content=EXTRACTION_PROMPT)] + list(messages)
        )

        # Filter to valid categories
        valid_insights = [
            i for i in result.insights
            if i.category in ALLOWED_CATEGORIES
        ]

        if not valid_insights:
            return {}

        # Persist via async bridge
        from app.db.session import async_session_factory
        from app.db.repository import (
            upsert_patient_insight,
            decay_unreinforced_insights,
        )

        async def _persist():
            async with async_session_factory() as session:
                reinforced_ids = []
                for insight in valid_insights:
                    row = await upsert_patient_insight(
                        session, patient_id, insight.category, insight.content
                    )
                    reinforced_ids.append(row.insight_id)
                await decay_unreinforced_insights(
                    session, patient_id, reinforced_ids
                )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(lambda: asyncio.run(_persist())).result()
            else:
                loop.run_until_complete(_persist())
        except RuntimeError:
            asyncio.run(_persist())

        logger.info(
            "Extracted %d insights for patient %s",
            len(valid_insights),
            patient_id,
        )
    except Exception:
        logger.exception("Insight extraction failed for patient %s", patient_id)

    return {}
