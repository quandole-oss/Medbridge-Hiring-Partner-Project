import datetime

import pytest

from app.db.models import (
    Exercise,
    ExerciseCompletion,
    OutcomeReport,
    Patient,
    Pathway,
    PathwayWeek,
)


async def _setup_pathway(db_session):
    """Create a pathway with 4 weeks and a patient assigned to it."""
    pathway = Pathway(
        name="Test Pathway",
        description="Test",
        total_weeks=4,
        condition="knee",
        is_active=True,
    )
    db_session.add(pathway)
    await db_session.flush()

    weeks = [
        (1, "Foundation", 0.6, None),
        (2, "Building", 0.7, 6),
        (3, "Strengthening", 0.75, 5),
        (4, "Integration", 0.8, 4),
    ]
    for wn, theme, threshold, pain in weeks:
        pw = PathwayWeek(
            pathway_id=pathway.pathway_id,
            week_number=wn,
            theme=theme,
            advancement_threshold=threshold,
            pain_ceiling=pain,
        )
        db_session.add(pw)
    await db_session.flush()

    now = datetime.datetime.now(datetime.timezone.utc)
    patient = Patient(
        patient_id="p1",
        consent_status=True,
        enrollment_date=now - datetime.timedelta(days=4),
        current_phase="active",
        pathway_id=pathway.pathway_id,
        current_week=1,
    )
    db_session.add(patient)
    await db_session.flush()

    # Add 3 exercises for week 1
    for i in range(1, 4):
        ex = Exercise(
            patient_id="p1",
            name=f"Exercise {i}",
            body_part="Knee",
            sets=3,
            reps=10,
            day_number=1,
            week_number=1,
            sort_order=i,
        )
        db_session.add(ex)
    await db_session.flush()
    await db_session.commit()
    return pathway


@pytest.mark.asyncio
async def test_pathway_status(client, db_session, api_headers):
    await _setup_pathway(db_session)

    response = await client.get("/patients/p1/pathway", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["pathway_name"] == "Test Pathway"
    assert data["current_week"] == 1
    assert data["total_weeks"] == 4
    assert data["week_theme"] == "Foundation"
    assert data["advancement_threshold"] == 0.6


@pytest.mark.asyncio
async def test_advancement_success(client, db_session, api_headers):
    await _setup_pathway(db_session)

    # Complete all 3 exercises (100% adherence, well above 60% threshold)
    from sqlalchemy import select
    result = await db_session.execute(
        select(Exercise).where(Exercise.patient_id == "p1", Exercise.week_number == 1)
    )
    exercises = list(result.scalars().all())

    # Get the patient to determine day 1's date (exercises are day_number=1)
    patient = await db_session.execute(
        select(Patient).where(Patient.patient_id == "p1")
    )
    patient = patient.scalar_one()
    enrollment_date = patient.enrollment_date
    if hasattr(enrollment_date, 'date'):
        enrollment_date = enrollment_date.date()
    day1_date = enrollment_date  # day_number=1 corresponds to enrollment date

    for ex in exercises:
        comp = ExerciseCompletion(
            patient_id="p1",
            exercise_id=ex.exercise_id,
            completed_date=day1_date,
            sets_completed=ex.sets,
            set_statuses=["complete"] * ex.sets,
        )
        db_session.add(comp)
    await db_session.commit()

    response = await client.post("/patients/p1/pathway/advance", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["advanced"] is True
    assert data["new_week"] == 2


@pytest.mark.asyncio
async def test_advancement_blocked_by_adherence(client, db_session, api_headers):
    await _setup_pathway(db_session)
    # No exercises completed -> 0% adherence, below 60% threshold

    response = await client.post("/patients/p1/pathway/advance", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["advanced"] is False
    assert data["reason"] == "adherence"


@pytest.mark.asyncio
async def test_advancement_blocked_by_pain(client, db_session, api_headers):
    await _setup_pathway(db_session)

    # Move patient to week 2 (which has pain_ceiling=6)
    from sqlalchemy import select
    result = await db_session.execute(
        select(Patient).where(Patient.patient_id == "p1")
    )
    patient = result.scalar_one()
    patient.current_week = 2
    await db_session.flush()

    # Add exercises for week 2
    for i in range(1, 4):
        ex = Exercise(
            patient_id="p1",
            name=f"Week2 Ex {i}",
            body_part="Knee",
            sets=3,
            reps=10,
            day_number=1,
            week_number=2,
            sort_order=i,
        )
        db_session.add(ex)
    await db_session.flush()

    # Complete all week 2 exercises (meet adherence threshold)
    # Exercises are day_number=1, so use enrollment date (day 1's date)
    enrollment_date = patient.enrollment_date
    if hasattr(enrollment_date, 'date'):
        enrollment_date = enrollment_date.date()

    result2 = await db_session.execute(
        select(Exercise).where(Exercise.patient_id == "p1", Exercise.week_number == 2)
    )
    for ex in result2.scalars().all():
        comp = ExerciseCompletion(
            patient_id="p1",
            exercise_id=ex.exercise_id,
            completed_date=enrollment_date,
            sets_completed=ex.sets,
            set_statuses=["complete"] * ex.sets,
        )
        db_session.add(comp)

    # Submit a high pain score (8 > ceiling of 6)
    report = OutcomeReport(
        patient_id="p1",
        report_date=datetime.date.today(),
        pain_score=8,
        function_score=5,
        wellbeing_score=5,
    )
    db_session.add(report)
    await db_session.commit()

    response = await client.post("/patients/p1/pathway/advance", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["advanced"] is False
    assert data["reason"] == "pain"


@pytest.mark.asyncio
async def test_exercises_filtered_by_week(client, db_session, api_headers):
    await _setup_pathway(db_session)

    # Add exercises for week 2
    for i in range(1, 3):
        ex = Exercise(
            patient_id="p1",
            name=f"Week2 Ex {i}",
            body_part="Knee",
            sets=4,
            reps=12,
            day_number=1,
            week_number=2,
            sort_order=i,
        )
        db_session.add(ex)
    await db_session.commit()

    # Patient is on week 1, should only see week 1 exercises
    response = await client.get(
        "/patients/p1/exercises?day=1", headers=api_headers
    )
    assert response.status_code == 200
    data = response.json()
    names = [e["name"] for e in data["exercises"]]
    assert all("Week2" not in n for n in names)
    assert len(data["exercises"]) == 3  # 3 week-1 exercises
