import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.db.models import Exercise, Goal, Patient


@pytest.mark.asyncio
async def test_create_goal_with_target_date(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.commit()

    mock_result = []
    with patch(
        "app.services.exercise_generator.generate_and_persist_exercises",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = await client.post(
            "/patients/p1/goals",
            json={"goal_text": "Walk without cane", "target_date": "2026-06-15"},
            headers=api_headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["goal_text"] == "Walk without cane"
    assert data["target_date"] == "2026-06-15"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_goal_generates_exercises(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.commit()

    # Create mock exercises to be returned
    mock_exercises = [
        Exercise(
            exercise_id=100, patient_id="p1", name="Test Ex", body_part="Knee",
            sets=3, reps=10, day_number=1, sort_order=10, goal_id=1,
        ),
        Exercise(
            exercise_id=101, patient_id="p1", name="Test Ex 2", body_part="Knee",
            sets=2, reps=8, day_number=2, sort_order=11, goal_id=1,
        ),
    ]

    with patch(
        "app.services.exercise_generator.generate_and_persist_exercises",
        new_callable=AsyncMock,
        return_value=mock_exercises,
    ):
        response = await client.post(
            "/patients/p1/goals",
            json={"goal_text": "Reduce knee pain"},
            headers=api_headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["exercise_count"] == 2


@pytest.mark.asyncio
async def test_create_goal_max_3_enforced(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.commit()

    # Create 3 existing goals
    for i in range(3):
        goal = Goal(patient_id="p1", goal_text=f"Goal {i}", is_active=True)
        db_session.add(goal)
    await db_session.commit()

    response = await client.post(
        "/patients/p1/goals",
        json={"goal_text": "Fourth goal"},
        headers=api_headers,
    )

    assert response.status_code == 422
    assert "Maximum 3 active goals" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_goals_returns_all_active(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.commit()

    g1 = Goal(patient_id="p1", goal_text="Goal A", is_active=True)
    g2 = Goal(patient_id="p1", goal_text="Goal B", is_active=True,
              target_date=datetime.date(2026, 6, 15))
    g3 = Goal(patient_id="p1", goal_text="Goal C", is_active=False)
    db_session.add_all([g1, g2, g3])
    await db_session.commit()

    response = await client.get("/patients/p1/goals", headers=api_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    texts = {g["goal_text"] for g in data}
    assert "Goal A" in texts
    assert "Goal B" in texts
    assert "Goal C" not in texts


@pytest.mark.asyncio
async def test_delete_goal_deactivates_exercises(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.commit()

    goal = Goal(patient_id="p1", goal_text="Test goal", is_active=True)
    db_session.add(goal)
    await db_session.flush()

    ex = Exercise(
        patient_id="p1", name="Goal Ex", body_part="Knee",
        sets=3, reps=10, day_number=1, sort_order=10,
        goal_id=goal.goal_id, is_active=True,
    )
    db_session.add(ex)
    await db_session.commit()

    response = await client.delete(
        f"/patients/p1/goals/{goal.goal_id}",
        headers=api_headers,
    )

    assert response.status_code == 204

    # Verify goal is deactivated
    await db_session.refresh(goal)
    assert goal.is_active is False

    # Verify exercise is deactivated
    await db_session.refresh(ex)
    assert ex.is_active is False


@pytest.mark.asyncio
async def test_update_goal_target_date(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.commit()

    goal = Goal(patient_id="p1", goal_text="Original goal", is_active=True)
    db_session.add(goal)
    await db_session.commit()

    response = await client.patch(
        f"/patients/p1/goals/{goal.goal_id}",
        json={"target_date": "2026-09-01", "goal_text": "Updated goal"},
        headers=api_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["goal_text"] == "Updated goal"
    assert data["target_date"] == "2026-09-01"


@pytest.mark.asyncio
async def test_exercises_include_goal_attribution(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.commit()

    goal = Goal(patient_id="p1", goal_text="Knee recovery", is_active=True)
    db_session.add(goal)
    await db_session.flush()

    # Exercise with goal
    ex1 = Exercise(
        patient_id="p1", name="Goal Ex", body_part="Knee",
        sets=3, reps=10, day_number=1, sort_order=1,
        goal_id=goal.goal_id, is_active=True,
    )
    # Exercise without goal (baseline)
    ex2 = Exercise(
        patient_id="p1", name="Baseline Ex", body_part="Ankle",
        sets=2, reps=10, day_number=1, sort_order=2,
        is_active=True,
    )
    db_session.add_all([ex1, ex2])
    await db_session.commit()

    response = await client.get(
        "/patients/p1/exercises?day=1",
        headers=api_headers,
    )

    assert response.status_code == 200
    data = response.json()
    exercises = data["exercises"]
    assert len(exercises) == 2

    goal_ex = next(e for e in exercises if e["name"] == "Goal Ex")
    assert goal_ex["goal_id"] == goal.goal_id
    assert goal_ex["goal_text"] == "Knee recovery"

    baseline_ex = next(e for e in exercises if e["name"] == "Baseline Ex")
    assert baseline_ex["goal_id"] is None
    assert baseline_ex["goal_text"] is None


@pytest.mark.asyncio
async def test_patient_status_includes_goals(client, db_session, api_headers):
    patient = Patient(
        patient_id="p1", consent_status=True, current_phase="active",
        enrollment_date=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(patient)
    await db_session.commit()

    goal = Goal(patient_id="p1", goal_text="Test goal", is_active=True)
    db_session.add(goal)
    await db_session.commit()

    response = await client.get("/patients/p1/status", headers=api_headers)

    assert response.status_code == 200
    data = response.json()
    assert "goals" in data
    assert len(data["goals"]) == 1
    assert data["goals"][0]["goal_text"] == "Test goal"
