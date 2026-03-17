import pytest

from app.db.models import Patient
from app.graph.state import Phase


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_chat_requires_api_key(client):
    response = await client.post("/chat", json={
        "patient_id": "p1",
        "message": "hello",
    })
    assert response.status_code == 422  # missing header


@pytest.mark.asyncio
async def test_chat_rejects_invalid_api_key(client):
    response = await client.post(
        "/chat",
        json={"patient_id": "p1", "message": "hello"},
        headers={"X-Api-Key": "wrong-key"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_rejects_unconsented_patient(client, db_session, api_headers):
    patient = Patient(patient_id="p1", consent_status=False, current_phase="pending")
    db_session.add(patient)
    await db_session.commit()

    response = await client.post(
        "/chat",
        json={"patient_id": "p1", "message": "hello"},
        headers=api_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_chat_rejects_unknown_patient(client, api_headers):
    response = await client.post(
        "/chat",
        json={"patient_id": "unknown", "message": "hello"},
        headers=api_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_consent_grant(client, db_session, api_headers):
    patient = Patient(patient_id="p1", consent_status=False, current_phase="pending")
    db_session.add(patient)
    await db_session.commit()

    response = await client.post(
        "/events/trigger",
        json={"patient_id": "p1", "event_type": "consent_granted"},
        headers=api_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["new_phase"] == "onboarding"


@pytest.mark.asyncio
async def test_consent_grant_idempotent(client, db_session, api_headers):
    patient = Patient(patient_id="p1", consent_status=True, current_phase="active")
    db_session.add(patient)
    await db_session.commit()

    response = await client.post(
        "/events/trigger",
        json={"patient_id": "p1", "event_type": "consent_granted"},
        headers=api_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "Consent already granted" in data["message"]


@pytest.mark.asyncio
async def test_invalid_event_returns_422(client, db_session, api_headers):
    patient = Patient(patient_id="p1", consent_status=True, current_phase="active")
    db_session.add(patient)
    await db_session.commit()

    response = await client.post(
        "/events/trigger",
        json={"patient_id": "p1", "event_type": "manual_phase_override"},
        headers=api_headers,
    )
    assert response.status_code == 422
    assert "Invalid transition" in response.json()["detail"]


@pytest.mark.asyncio
async def test_patient_status(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1",
        consent_status=True,
        current_phase="active",
        unanswered_count=1,
    )
    db_session.add(patient)
    await db_session.commit()

    response = await client.get("/patients/p1/status", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["current_phase"] == "active"
    assert data["unanswered_count"] == 1


@pytest.mark.asyncio
async def test_patient_status_not_found(client, api_headers):
    response = await client.get("/patients/unknown/status", headers=api_headers)
    assert response.status_code == 404
