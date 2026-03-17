import datetime

import pytest

from app.db.models import OutcomeReport, Patient


@pytest.mark.asyncio
async def test_submit_outcome_report(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.commit()

    response = await client.post(
        "/patients/p1/outcomes",
        json={"pain_score": 5, "function_score": 7, "wellbeing_score": 6, "notes": "Feeling ok"},
        headers=api_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["pain_score"] == 5
    assert data["function_score"] == 7
    assert data["wellbeing_score"] == 6
    assert data["notes"] == "Feeling ok"
    assert data["patient_id"] == "p1"
    assert "report_id" in data


@pytest.mark.asyncio
async def test_submit_outcome_invalid_range(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.commit()

    response = await client.post(
        "/patients/p1/outcomes",
        json={"pain_score": 11, "function_score": 5, "wellbeing_score": 5},
        headers=api_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_outcome_summary_empty(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.commit()

    response = await client.get("/patients/p1/outcomes", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["report_count"] == 0
    assert data["latest"] is None
    assert data["reports"] == []


async def _create_patient_with_reports(db_session, patient_id, pain_scores,
                                      function_scores=None, wellbeing_scores=None):
    """Helper to create a patient with outcome reports."""
    n = len(pain_scores)
    if function_scores is None:
        function_scores = [5] * n
    if wellbeing_scores is None:
        wellbeing_scores = [5] * n

    patient = Patient(
        patient_id=patient_id, consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.flush()

    today = datetime.date.today()
    for i in range(n):
        report = OutcomeReport(
            patient_id=patient_id,
            report_date=today - datetime.timedelta(days=n - 1 - i),
            pain_score=pain_scores[i],
            function_score=function_scores[i],
            wellbeing_score=wellbeing_scores[i],
        )
        db_session.add(report)
    await db_session.commit()


@pytest.mark.asyncio
async def test_outcome_trends_improving(client, db_session, api_headers):
    # Pain declining (7 -> 5 -> 3) = improving
    await _create_patient_with_reports(db_session, "p1", [7, 5, 3])

    response = await client.get("/patients/p1/outcomes", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["report_count"] == 3
    assert data["pain_trend"] == "improving"


@pytest.mark.asyncio
async def test_outcome_trends_stable(client, db_session, api_headers):
    await _create_patient_with_reports(db_session, "p1", [5, 5, 5])

    response = await client.get("/patients/p1/outcomes", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["pain_trend"] == "stable"


@pytest.mark.asyncio
async def test_outcome_trends_declining(client, db_session, api_headers):
    # Pain increasing (3 -> 5 -> 7) = declining
    await _create_patient_with_reports(db_session, "p1", [3, 5, 7])

    response = await client.get("/patients/p1/outcomes", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["pain_trend"] == "declining"


@pytest.mark.asyncio
async def test_outcome_trends_function_and_wellbeing(client, db_session, api_headers):
    # Function improving (3 -> 5 -> 7), wellbeing declining (7 -> 5 -> 3)
    await _create_patient_with_reports(
        db_session, "p1",
        pain_scores=[5, 5, 5],
        function_scores=[3, 5, 7],
        wellbeing_scores=[7, 5, 3],
    )

    response = await client.get("/patients/p1/outcomes", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["function_trend"] == "improving"
    assert data["wellbeing_trend"] == "declining"
