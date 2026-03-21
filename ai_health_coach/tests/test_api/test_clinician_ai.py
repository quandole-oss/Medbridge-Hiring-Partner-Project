"""Tests for clinician AI features: risk scoring, patient summary, caseload briefing."""
import datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.db.models import Patient
from app.services.risk_scoring import compute_risk_score


# ── Risk Scoring Unit Tests (pure function, no mocks) ────────────────────────


class TestComputeRiskScore:
    def _defaults(self, **overrides):
        base = {
            "adherence": {
                "completion_rate": 80,
                "streak": 5,
                "days_in_program": 7,
            },
            "outcomes": {"pain_trend": "improving", "latest": {"pain_score": 3}},
            "difficulty": {"too_hard": 0, "too_easy": 0, "just_right": 5},
            "phase": "active",
            "days_since_last_message": 0,
            "open_alert_counts": {"critical": 0, "high": 0, "low": 0},
        }
        base.update(overrides)
        return base

    def test_healthy_patient_low_risk(self):
        result = compute_risk_score(**self._defaults())
        assert result["level"] == "low"
        assert result["score"] <= 20

    def test_low_adherence_high_risk(self):
        result = compute_risk_score(**self._defaults(
            adherence={"completion_rate": 20, "streak": 0, "days_in_program": 7},
            outcomes={"pain_trend": "declining", "latest": {"pain_score": 8}},
        ))
        assert result["level"] in ("high", "critical")
        assert result["score"] > 45

    def test_dormant_adds_points(self):
        base = compute_risk_score(**self._defaults(phase="active"))
        dormant = compute_risk_score(**self._defaults(phase="dormant"))
        assert dormant["score"] > base["score"]
        assert dormant["factors"]["phase"] == 10

    def test_inactivity_scoring(self):
        result = compute_risk_score(**self._defaults(days_since_last_message=8))
        assert result["factors"]["inactivity"] == 15

    def test_difficulty_too_hard(self):
        result = compute_risk_score(**self._defaults(
            difficulty={"too_hard": 6, "too_easy": 0, "just_right": 2}
        ))
        assert result["factors"]["difficulty"] == 15

    def test_critical_alert_adds_points(self):
        result = compute_risk_score(**self._defaults(
            open_alert_counts={"critical": 1, "high": 0, "low": 0}
        ))
        assert result["factors"]["alerts"] == 5

    def test_level_boundaries(self):
        # Low boundary
        result = compute_risk_score(**self._defaults())
        assert result["score"] <= 20
        assert result["level"] == "low"

    def test_zero_streak_adds_points(self):
        result = compute_risk_score(**self._defaults(
            adherence={"completion_rate": 80, "streak": 0, "days_in_program": 7}
        ))
        assert result["factors"]["streak"] == 10

    def test_factors_dict_has_all_keys(self):
        result = compute_risk_score(**self._defaults())
        expected_keys = {
            "adherence", "pain_trend", "inactivity", "difficulty",
            "phase", "streak", "alerts",
        }
        assert set(result["factors"].keys()) == expected_keys

    def test_score_capped_at_100(self):
        # Worst case scenario
        result = compute_risk_score(
            adherence={"completion_rate": 0, "streak": 0, "days_in_program": 7},
            outcomes={"pain_trend": "declining", "latest": {"pain_score": 10}},
            difficulty={"too_hard": 10, "too_easy": 0, "just_right": 0},
            phase="dormant",
            days_since_last_message=14,
            open_alert_counts={"critical": 2, "high": 0, "low": 0},
        )
        assert result["score"] <= 100
        assert result["level"] == "critical"


# ── API Endpoint Tests ───────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def ai_patient(db_session):
    now = datetime.datetime.now(datetime.timezone.utc)
    patient = Patient(
        patient_id="ai-test-patient",
        consent_status=True,
        enrollment_date=now - datetime.timedelta(days=5),
        last_message_at=now - datetime.timedelta(hours=1),
        current_phase="active",
    )
    db_session.add(patient)
    await db_session.commit()
    return patient


@pytest.mark.asyncio
async def test_patient_ai_summary_returns_200(
    client, clinician, clinician_headers, ai_patient
):
    mock_response = AsyncMock()
    mock_response.content = "Test AI summary text."

    with patch(
        "app.services.clinician_ai.get_safety_llm"
    ) as mock_llm:
        mock_instance = AsyncMock()
        mock_instance.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.return_value = mock_instance

        resp = await client.get(
            "/clinician/patients/ai-test-patient/ai-summary",
            headers=clinician_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == "ai-test-patient"
    assert "risk_score" in data
    assert data["risk_level"] in ("low", "medium", "high", "critical")
    assert "risk_factors" in data
    assert "summary" in data


@pytest.mark.asyncio
async def test_patient_ai_summary_cached(
    client, clinician, clinician_headers, ai_patient
):
    mock_response = AsyncMock()
    mock_response.content = "Test AI summary text."

    with patch(
        "app.services.clinician_ai.get_safety_llm"
    ) as mock_llm:
        mock_instance = AsyncMock()
        mock_instance.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.return_value = mock_instance

        # First call generates
        resp1 = await client.get(
            "/clinician/patients/ai-test-patient/ai-summary",
            headers=clinician_headers,
        )
        assert resp1.status_code == 200
        assert resp1.json()["is_cached"] is False

        # Second call uses cache
        resp2 = await client.get(
            "/clinician/patients/ai-test-patient/ai-summary",
            headers=clinician_headers,
        )
        assert resp2.status_code == 200
        assert resp2.json()["is_cached"] is True


@pytest.mark.asyncio
async def test_patient_ai_summary_not_found(
    client, clinician, clinician_headers
):
    resp = await client.get(
        "/clinician/patients/nonexistent/ai-summary",
        headers=clinician_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patient_ai_summary_no_auth(client, ai_patient):
    resp = await client.get(
        "/clinician/patients/ai-test-patient/ai-summary",
        headers={"X-Api-Key": "wrong-key"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_caseload_briefing_returns_200(
    client, clinician, clinician_headers, ai_patient
):
    mock_response = AsyncMock()
    mock_response.content = "Test caseload briefing text."

    with patch(
        "app.services.clinician_ai.get_safety_llm"
    ) as mock_llm:
        mock_instance = AsyncMock()
        mock_instance.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.return_value = mock_instance

        resp = await client.get(
            "/clinician/caseload-briefing",
            headers=clinician_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_count"] >= 1
    assert "briefing" in data
    assert "high_risk_count" in data


@pytest.mark.asyncio
async def test_caseload_briefing_cached(
    client, clinician, clinician_headers, ai_patient
):
    mock_response = AsyncMock()
    mock_response.content = "Test caseload briefing text."

    with patch(
        "app.services.clinician_ai.get_safety_llm"
    ) as mock_llm:
        mock_instance = AsyncMock()
        mock_instance.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.return_value = mock_instance

        resp1 = await client.get(
            "/clinician/caseload-briefing",
            headers=clinician_headers,
        )
        assert resp1.json()["is_cached"] is False

        resp2 = await client.get(
            "/clinician/caseload-briefing",
            headers=clinician_headers,
        )
        assert resp2.json()["is_cached"] is True
