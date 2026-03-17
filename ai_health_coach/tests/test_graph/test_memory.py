import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, HumanMessage

from app.db.models import Patient, PatientInsight
from app.db.repository import (
    decay_unreinforced_insights,
    get_patient_insights_db,
    upsert_patient_insight,
)
from app.graph.nodes.memory import extract_insights_node


# ── Helpers ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def patient(db_session):
    p = Patient(patient_id="test-memory-patient", consent_status=True)
    db_session.add(p)
    await db_session.commit()
    return p


# ── Repository tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_creates_new_insight(db_session, patient):
    insight = await upsert_patient_insight(
        db_session, patient.patient_id, "motivation", "Wants to play with kids"
    )
    assert insight.confidence == pytest.approx(0.7)
    assert insight.times_reinforced == 0
    assert insight.is_active is True


@pytest.mark.asyncio
async def test_upsert_reinforces_existing(db_session, patient):
    await upsert_patient_insight(
        db_session, patient.patient_id, "motivation", "Wants to play with kids"
    )
    reinforced = await upsert_patient_insight(
        db_session, patient.patient_id, "motivation", "Wants to play with kids"
    )
    assert reinforced.confidence == pytest.approx(0.8)
    assert reinforced.times_reinforced == 1
    assert reinforced.last_reinforced_at is not None


@pytest.mark.asyncio
async def test_get_insights_ordered_by_confidence(db_session, patient):
    pid = patient.patient_id
    i1 = await upsert_patient_insight(db_session, pid, "barrier", "Low insight")
    i1.confidence = 0.4
    await db_session.commit()

    i2 = await upsert_patient_insight(db_session, pid, "motivation", "High insight")
    i2.confidence = 0.9
    await db_session.commit()

    i3 = await upsert_patient_insight(db_session, pid, "preference", "Mid insight")
    i3.confidence = 0.6
    await db_session.commit()

    results = await get_patient_insights_db(db_session, pid)
    confidences = [r.confidence for r in results]
    assert confidences == sorted(confidences, reverse=True)


@pytest.mark.asyncio
async def test_get_insights_filters_low_confidence(db_session, patient):
    insight = await upsert_patient_insight(
        db_session, patient.patient_id, "barrier", "Very uncertain"
    )
    insight.confidence = 0.1
    await db_session.commit()

    results = await get_patient_insights_db(db_session, patient.patient_id)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_get_insights_respects_limit(db_session, patient):
    pid = patient.patient_id
    for i in range(15):
        await upsert_patient_insight(db_session, pid, "preference", f"Insight {i}")

    results = await get_patient_insights_db(db_session, pid, limit=10)
    assert len(results) == 10


@pytest.mark.asyncio
async def test_decay_reduces_confidence(db_session, patient):
    pid = patient.patient_id
    i1 = await upsert_patient_insight(db_session, pid, "motivation", "Keep up with kids")
    i2 = await upsert_patient_insight(db_session, pid, "barrier", "Morning stiffness")
    i3 = await upsert_patient_insight(db_session, pid, "preference", "Likes mornings")

    # Decay all except i1
    await decay_unreinforced_insights(db_session, pid, [i1.insight_id])

    await db_session.refresh(i2)
    await db_session.refresh(i3)

    assert i2.confidence == pytest.approx(0.65)
    assert i3.confidence == pytest.approx(0.65)

    # i1 should be unchanged
    await db_session.refresh(i1)
    assert i1.confidence == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_decay_deactivates_very_low(db_session, patient):
    insight = await upsert_patient_insight(
        db_session, patient.patient_id, "barrier", "Old barrier"
    )
    insight.confidence = 0.1
    await db_session.commit()

    await decay_unreinforced_insights(db_session, patient.patient_id, [])

    await db_session.refresh(insight)
    assert insight.is_active is False


# ── Node tests (no DB, no LLM) ──────────────────────────────────────────────


def test_extract_node_skips_no_user_messages():
    state = {
        "patient_id": "test-patient",
        "messages": [AIMessage(content="Hello!")],
    }
    result = extract_insights_node(state)
    assert result == {}
