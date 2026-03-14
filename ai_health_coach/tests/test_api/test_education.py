import datetime

import pytest

from app.db.models import EducationContent, Exercise, Patient


@pytest.mark.asyncio
async def test_get_education_for_day(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.flush()

    # Add an exercise for day 1 with body_part Ankle
    exercise = Exercise(
        patient_id="p1", name="Ankle Pumps", body_part="Ankle",
        sets=3, reps=10, day_number=1, sort_order=1,
    )
    db_session.add(exercise)

    # Add education content matching day 1 theme (mobility)
    content = EducationContent(
        title="Why ankle mobility matters",
        body="Ankle mobility helps recovery.",
        content_type="article",
        body_part="Ankle",
        day_theme="mobility",
        sort_order=1,
        is_active=True,
    )
    db_session.add(content)
    await db_session.commit()

    response = await client.get(
        "/patients/p1/education?day=1", headers=api_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["title"] == "Why ankle mobility matters"
    assert data[0]["is_viewed"] is False


@pytest.mark.asyncio
async def test_mark_viewed(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.flush()

    exercise = Exercise(
        patient_id="p1", name="Ankle Pumps", body_part="Ankle",
        sets=3, reps=10, day_number=1, sort_order=1,
    )
    db_session.add(exercise)

    content = EducationContent(
        title="Test Article",
        body="Body text.",
        content_type="article",
        body_part="Ankle",
        day_theme="mobility",
        sort_order=1,
        is_active=True,
    )
    db_session.add(content)
    await db_session.commit()

    # Mark as viewed
    view_resp = await client.post(
        f"/patients/p1/education/{content.content_id}/view",
        headers=api_headers,
    )
    assert view_resp.status_code == 204

    # Now GET should show is_viewed=True
    response = await client.get(
        "/patients/p1/education?day=1", headers=api_headers
    )
    data = response.json()
    assert len(data) >= 1
    assert data[0]["is_viewed"] is True


@pytest.mark.asyncio
async def test_education_empty_day(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.commit()

    # No education content seeded — should return empty list
    response = await client.get(
        "/patients/p1/education?day=3", headers=api_headers
    )
    assert response.status_code == 200
    assert response.json() == []
