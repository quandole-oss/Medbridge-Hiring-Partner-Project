"""End-to-end test: adherence stats dates must match exercise completion dates.

Regression test for the bug where get_adherence_stats() computed check dates
relative to *today* instead of *enrollment_date*, causing daily progress and
adherence heatmap to show 0% for days that have completions once
days_in_program > 7.
"""

import datetime

import pytest
import pytest_asyncio

from app.db.models import Exercise, ExerciseCompletion, Patient


@pytest_asyncio.fixture
async def old_patient(db_session):
    """Patient enrolled 18 days ago (days_in_program >> 7)."""
    enrollment = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=18
    )
    patient = Patient(
        patient_id="old-pt",
        consent_status=True,
        current_phase="active",
        enrollment_date=enrollment,
    )
    db_session.add(patient)

    # Create one exercise per day for days 1-7
    exercises = []
    for day in range(1, 8):
        ex = Exercise(
            patient_id="old-pt",
            name=f"Exercise Day {day}",
            body_part="knee",
            sets=3,
            reps=10,
            day_number=day,
            week_number=1,
            sort_order=0,
            is_active=True,
        )
        db_session.add(ex)
        exercises.append(ex)

    await db_session.flush()

    # Complete exercises for days 1-5 using enrollment-relative dates
    # (this matches how the API marks completions)
    enrollment_date = enrollment.date()
    for i, day in enumerate(range(1, 6)):
        completion_date = enrollment_date + datetime.timedelta(days=day - 1)
        comp = ExerciseCompletion(
            patient_id="old-pt",
            exercise_id=exercises[i].exercise_id,
            completed_date=completion_date,
            sets_completed=3,
            set_statuses=["complete", "complete", "complete"],
        )
        db_session.add(comp)

    await db_session.commit()
    return patient


@pytest.mark.asyncio
async def test_adherence_stats_match_completions(client, old_patient, api_headers):
    """Daily completions in adherence stats should reflect actual completions.

    Before the fix, all days showed 0% because the stats function looked up
    dates relative to today instead of enrollment_date.
    """
    resp = await client.get("/patients/old-pt/adherence", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()

    daily = {d["day"]: d for d in data["daily_completions"]}

    # Days 1-5 each had one exercise completed out of one
    for day in range(1, 6):
        assert daily[day]["completed"] == 1, (
            f"Day {day}: expected 1 completion but got {daily[day]['completed']}"
        )

    # Days 6-7 had no completions
    for day in range(6, 8):
        assert daily[day]["completed"] == 0

    # Overall: 5 completed out of 7 due
    assert data["total_completed"] == 5
    assert data["total_due"] == 7


@pytest.mark.asyncio
async def test_exercise_list_agrees_with_adherence(
    client, old_patient, api_headers
):
    """The exercise GET endpoint and adherence stats should report the same
    completion status for every day."""
    adherence_resp = await client.get(
        "/patients/old-pt/adherence", headers=api_headers
    )
    adherence_daily = {
        d["day"]: d for d in adherence_resp.json()["daily_completions"]
    }

    for day in range(1, 8):
        ex_resp = await client.get(
            f"/patients/old-pt/exercises?day={day}", headers=api_headers
        )
        assert ex_resp.status_code == 200
        exercises = ex_resp.json()["exercises"]
        api_completed = sum(1 for e in exercises if e.get("is_completed"))
        adherence_completed = adherence_daily[day]["completed"]

        assert api_completed == adherence_completed, (
            f"Day {day}: exercise endpoint says {api_completed} completed, "
            f"adherence says {adherence_completed}"
        )
