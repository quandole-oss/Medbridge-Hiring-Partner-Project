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


@pytest.mark.asyncio
async def test_outcome_trends(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.flush()

    today = datetime.date.today()
    # Create reports with declining pain (7 -> 5 -> 3)
    for i, pain in enumerate([7, 5, 3]):
        report = OutcomeReport(
            patient_id="p1",
            report_date=today - datetime.timedelta(days=2 - i),
            pain_score=pain,
            function_score=5,
            wellbeing_score=5,
        )
        db_session.add(report)
    await db_session.commit()

    response = await client.get("/patients/p1/outcomes", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["report_count"] == 3
    assert data["pain_trend"] == "improving"  # pain went down = improving
