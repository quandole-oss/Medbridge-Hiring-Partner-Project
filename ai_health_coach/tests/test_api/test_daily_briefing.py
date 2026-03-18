"""Tests for daily briefing endpoint."""
import datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.db.models import DailyBriefing, Patient
from app.db.repository import get_daily_briefing, save_daily_briefing


@pytest_asyncio.fixture
async def briefing_patient(db_session):
    """Create a patient with consent for briefing tests."""
    patient = Patient(
        patient_id="briefing-patient",
        consent_status=True,
        current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=5),
    )
    db_session.add(patient)
    await db_session.commit()
    return patient


@pytest.mark.asyncio
async def test_save_and_get_daily_briefing(db_session, briefing_patient):
    """Can save and retrieve a daily briefing."""
    today = datetime.date.today()
    saved = await save_daily_briefing(
        db_session, "briefing-patient", today, "Keep up the great work!"
    )
    assert saved.briefing_id is not None
    assert saved.message == "Keep up the great work!"

    retrieved = await get_daily_briefing(db_session, "briefing-patient", today)
    assert retrieved is not None
    assert retrieved.message == "Keep up the great work!"


@pytest.mark.asyncio
async def test_get_daily_briefing_returns_none_for_different_day(
    db_session, briefing_patient
):
    """Returns None when no briefing exists for the given date."""
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    result = await get_daily_briefing(db_session, "briefing-patient", yesterday)
    assert result is None


@pytest.mark.asyncio
async def test_daily_briefing_endpoint_returns_404_for_unknown_patient(
    client, api_headers, db_session
):
    """Returns 404 for unknown patient."""
    resp = await client.get(
        "/patients/nonexistent/daily-briefing",
        headers=api_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_daily_briefing_endpoint_returns_cached(
    client, api_headers, db_session, briefing_patient
):
    """Returns cached briefing if one exists for today."""
    today = datetime.date.today()
    await save_daily_briefing(
        db_session, "briefing-patient", today, "Cached message!"
    )

    resp = await client.get(
        "/patients/briefing-patient/daily-briefing",
        headers=api_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Cached message!"
    assert data["is_cached"] is True
    assert data["patient_id"] == "briefing-patient"
    assert data["date"] == today.isoformat()


@pytest.mark.asyncio
async def test_daily_briefing_endpoint_generates_fresh(
    client, api_headers, db_session, briefing_patient
):
    """Generates a fresh briefing when no cache exists, using mocked LLM."""
    mock_response = AsyncMock()
    mock_response.content = "Fresh daily message for you!"

    with patch(
        "app.services.daily_briefing.get_safety_llm"
    ) as mock_llm:
        mock_instance = mock_llm.return_value
        mock_instance.ainvoke = AsyncMock(return_value=mock_response)

        resp = await client.get(
            "/patients/briefing-patient/daily-briefing",
            headers=api_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_cached"] is False
    assert len(data["message"]) > 0

    # Verify it was cached for next time
    today = datetime.date.today()
    cached = await get_daily_briefing(db_session, "briefing-patient", today)
    assert cached is not None
