"""Tests for automatic exercise progression."""
import datetime

import pytest
import pytest_asyncio

from app.db.models import Exercise, ExerciseCompletion, Patient
from app.db.repository import (
    get_difficulty_pattern_summary,
    get_recent_difficulty_signals,
    log_audit_event,
    mark_exercise_complete,
)


@pytest_asyncio.fixture
async def patient_with_exercises(db_session):
    """Create a patient with exercises and consent."""
    patient = Patient(
        patient_id="prog-patient",
        consent_status=True,
        current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=3),
    )
    db_session.add(patient)
    await db_session.commit()

    exercises = []
    for day in range(1, 4):
        ex = Exercise(
            patient_id="prog-patient",
            name="Exercise Day {}".format(day),
            description="Test exercise",
            body_part="knee",
            sets=3,
            reps=10,
            day_number=day,
            sort_order=0,
            is_active=True,
        )
        db_session.add(ex)
        exercises.append(ex)
    await db_session.commit()
    for e in exercises:
        await db_session.refresh(e)
    return patient, exercises


@pytest.mark.asyncio
async def test_get_recent_difficulty_signals_empty(db_session, patient_with_exercises):
    """No signals returns empty list."""
    _, exercises = patient_with_exercises
    signals = await get_recent_difficulty_signals(
        db_session, "prog-patient", exercises[0].exercise_id, days=3, signal="too_hard"
    )
    assert signals == []


@pytest.mark.asyncio
async def test_get_recent_difficulty_signals_filters_correctly(
    db_session, patient_with_exercises
):
    """Only returns matching difficulty signals for the right exercise."""
    _, exercises = patient_with_exercises
    ex_id = exercises[0].exercise_id
    today = datetime.date.today()

    # Add two "too_hard" completions
    await mark_exercise_complete(
        db_session, "prog-patient", ex_id, today,
        sets_completed=2, difficulty="too_hard",
    )
    await mark_exercise_complete(
        db_session, "prog-patient", ex_id,
        today - datetime.timedelta(days=1),
        sets_completed=2, difficulty="too_hard",
    )
    # Add one "just_right" (should not match)
    await mark_exercise_complete(
        db_session, "prog-patient", exercises[1].exercise_id, today,
        sets_completed=3, difficulty="just_right",
    )

    signals = await get_recent_difficulty_signals(
        db_session, "prog-patient", ex_id, days=3, signal="too_hard"
    )
    assert len(signals) == 2


@pytest.mark.asyncio
async def test_get_recent_difficulty_signals_respects_day_window(
    db_session, patient_with_exercises
):
    """Old signals outside the window are excluded."""
    _, exercises = patient_with_exercises
    ex_id = exercises[0].exercise_id

    # Add a signal 5 days ago (outside 3-day window)
    old_date = datetime.date.today() - datetime.timedelta(days=5)
    await mark_exercise_complete(
        db_session, "prog-patient", ex_id, old_date,
        sets_completed=2, difficulty="too_hard",
    )

    signals = await get_recent_difficulty_signals(
        db_session, "prog-patient", ex_id, days=3, signal="too_hard"
    )
    assert len(signals) == 0


@pytest.mark.asyncio
async def test_get_difficulty_pattern_summary(db_session, patient_with_exercises):
    """Summary aggregates difficulty feedback correctly."""
    _, exercises = patient_with_exercises
    today = datetime.date.today()

    await mark_exercise_complete(
        db_session, "prog-patient", exercises[0].exercise_id, today,
        sets_completed=3, difficulty="too_hard",
    )
    await mark_exercise_complete(
        db_session, "prog-patient", exercises[1].exercise_id, today,
        sets_completed=3, difficulty="just_right",
    )
    await mark_exercise_complete(
        db_session, "prog-patient", exercises[2].exercise_id, today,
        sets_completed=3,  # no difficulty
    )

    summary = await get_difficulty_pattern_summary(db_session, "prog-patient", days=7)
    assert summary["too_hard"] == 1
    assert summary["just_right"] == 1
    assert summary["no_feedback"] == 1
    assert summary["too_easy"] == 0


@pytest.mark.asyncio
async def test_auto_adjust_below_threshold(db_session, patient_with_exercises):
    """Auto-adjust should not trigger with only 1 signal."""
    from app.services.exercise_progression import check_and_auto_adjust

    _, exercises = patient_with_exercises
    ex_id = exercises[0].exercise_id
    today = datetime.date.today()

    await mark_exercise_complete(
        db_session, "prog-patient", ex_id, today,
        sets_completed=2, difficulty="too_hard",
    )

    result = await check_and_auto_adjust(
        db_session, "prog-patient", ex_id, "too_hard"
    )
    assert result is None


@pytest.mark.asyncio
async def test_auto_adjust_ignores_just_right(db_session, patient_with_exercises):
    """Auto-adjust should not trigger for 'just_right' difficulty."""
    from app.services.exercise_progression import check_and_auto_adjust

    _, exercises = patient_with_exercises
    result = await check_and_auto_adjust(
        db_session, "prog-patient", exercises[0].exercise_id, "just_right"
    )
    assert result is None


@pytest.mark.asyncio
async def test_toggle_complete_returns_auto_adjusted_field(client, api_headers, db_session, patient_with_exercises):
    """Exercise completion response includes auto_adjusted field."""
    _, exercises = patient_with_exercises
    ex_id = exercises[0].exercise_id

    resp = await client.post(
        "/patients/prog-patient/exercises/complete",
        json={"exercise_id": ex_id, "difficulty": "just_right"},
        headers=api_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "auto_adjusted" in data
    assert data["auto_adjusted"] is None  # No threshold met
