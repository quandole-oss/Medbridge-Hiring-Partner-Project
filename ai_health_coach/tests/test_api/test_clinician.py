import datetime

import pytest
import pytest_asyncio

from app.db.models import ClinicalAlert, Patient
from app.db.repository import create_clinical_alert, log_audit_event


# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def demo_patient(db_session):
    now = datetime.datetime.now(datetime.timezone.utc)
    patient = Patient(
        patient_id="test-patient",
        consent_status=True,
        enrollment_date=now - datetime.timedelta(days=4),
        last_message_at=now - datetime.timedelta(hours=2),
        current_phase="active",
    )
    db_session.add(patient)
    await db_session.commit()
    return patient


@pytest_asyncio.fixture
async def demo_alerts(db_session, demo_patient):
    alerts = []
    for urgency, alert_type, status in [
        ("CRITICAL", "crisis", "open"),
        ("HIGH", "safety_violation", "open"),
        ("LOW", "disengagement", "acknowledged"),
    ]:
        alert = await create_clinical_alert(
            db_session,
            demo_patient.patient_id,
            alert_type,
            urgency,
            f"Test {urgency} alert",
        )
        if status != "open":
            alert.status = status
            alert.acknowledged_at = datetime.datetime.now(datetime.timezone.utc)
            await db_session.commit()
        alerts.append(alert)
    return alerts


# ── Auth Tests ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clinician_auth_valid(client, clinician, clinician_headers):
    resp = await client.get("/clinician/alerts/counts", headers=clinician_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_clinician_auth_invalid(client, clinician):
    resp = await client.get(
        "/clinician/alerts/counts", headers={"X-Api-Key": "wrong-key"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_clinician_auth_inactive(client, clinician, db_session):
    clinician.is_active = False
    await db_session.commit()
    resp = await client.get(
        "/clinician/alerts/counts",
        headers={"X-Api-Key": "test-clinician-key"},
    )
    assert resp.status_code == 401


# ── Alert CRUD Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_alerts(client, clinician, clinician_headers, demo_alerts):
    resp = await client.get("/clinician/alerts", headers=clinician_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


@pytest.mark.asyncio
async def test_list_alerts_filter_status(
    client, clinician, clinician_headers, demo_alerts
):
    resp = await client.get(
        "/clinician/alerts?status=open", headers=clinician_headers
    )
    data = resp.json()
    assert len(data) == 2
    assert all(a["status"] == "open" for a in data)


@pytest.mark.asyncio
async def test_list_alerts_filter_urgency(
    client, clinician, clinician_headers, demo_alerts
):
    resp = await client.get(
        "/clinician/alerts?urgency=CRITICAL", headers=clinician_headers
    )
    data = resp.json()
    assert len(data) == 1
    assert data[0]["urgency"] == "CRITICAL"


@pytest.mark.asyncio
async def test_alert_counts(client, clinician, clinician_headers, demo_alerts):
    resp = await client.get("/clinician/alerts/counts", headers=clinician_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2  # only open ones
    assert data["critical"] == 1
    assert data["high"] == 1
    assert data["low"] == 0


@pytest.mark.asyncio
async def test_patch_alert_acknowledge(
    client, clinician, clinician_headers, demo_alerts
):
    alert_id = demo_alerts[0].alert_id
    resp = await client.patch(
        f"/clinician/alerts/{alert_id}",
        headers=clinician_headers,
        json={"status": "acknowledged"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "acknowledged"
    assert data["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_patch_alert_resolve(
    client, clinician, clinician_headers, demo_alerts
):
    alert_id = demo_alerts[0].alert_id
    resp = await client.patch(
        f"/clinician/alerts/{alert_id}",
        headers=clinician_headers,
        json={"status": "resolved", "resolved_note": "Contacted patient directly"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["resolved_note"] == "Contacted patient directly"
    assert data["resolved_at"] is not None


@pytest.mark.asyncio
async def test_patch_alert_invalid_status(
    client, clinician, clinician_headers, demo_alerts
):
    alert_id = demo_alerts[0].alert_id
    resp = await client.patch(
        f"/clinician/alerts/{alert_id}",
        headers=clinician_headers,
        json={"status": "invalid"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_patch_alert_not_found(client, clinician, clinician_headers):
    resp = await client.patch(
        "/clinician/alerts/99999",
        headers=clinician_headers,
        json={"status": "acknowledged"},
    )
    assert resp.status_code == 404


# ── Patient Overview Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_patients(
    client, clinician, clinician_headers, demo_patient
):
    resp = await client.get("/clinician/patients", headers=clinician_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["patients"][0]["patient_id"] == "test-patient"
    assert data["patients"][0]["current_phase"] == "active"


@pytest.mark.asyncio
async def test_list_patients_filter_phase(
    client, clinician, clinician_headers, demo_patient
):
    resp = await client.get(
        "/clinician/patients?phase=dormant", headers=clinician_headers
    )
    data = resp.json()
    assert data["total"] == 0


# ── Patient Detail Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patient_detail(
    client, clinician, clinician_headers, demo_patient, demo_alerts
):
    resp = await client.get(
        "/clinician/patients/test-patient", headers=clinician_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == "test-patient"
    assert data["current_phase"] == "active"
    assert "adherence" in data
    assert "outcome_summary" in data
    assert "open_alerts" in data
    assert len(data["open_alerts"]) == 2  # only open alerts


@pytest.mark.asyncio
async def test_patient_detail_not_found(client, clinician, clinician_headers):
    resp = await client.get(
        "/clinician/patients/nonexistent", headers=clinician_headers
    )
    assert resp.status_code == 404


# ── Audit Log Tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_log(
    client, clinician, clinician_headers, demo_patient, db_session
):
    await log_audit_event(db_session, "test-patient", "test_event", {"key": "value"})
    await log_audit_event(db_session, "test-patient", "another_event", None)

    resp = await client.get(
        "/clinician/patients/test-patient/audit-log",
        headers=clinician_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_audit_log_filter_event_type(
    client, clinician, clinician_headers, demo_patient, db_session
):
    await log_audit_event(db_session, "test-patient", "test_event", {"key": "value"})
    await log_audit_event(db_session, "test-patient", "other_event", None)

    resp = await client.get(
        "/clinician/patients/test-patient/audit-log?event_type=test_event",
        headers=clinician_headers,
    )
    data = resp.json()
    assert len(data) == 1
    assert data[0]["event_type"] == "test_event"


# ── Cross-Patient Analytics Tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_adherence_heatmap(
    client, clinician, clinician_headers, demo_patient
):
    resp = await client.get(
        "/clinician/adherence-heatmap", headers=clinician_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "cells" in data


@pytest.mark.asyncio
async def test_outcome_trends(
    client, clinician, clinician_headers, demo_patient
):
    resp = await client.get(
        "/clinician/outcome-trends", headers=clinician_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "trends" in data
