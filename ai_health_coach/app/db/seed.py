import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Exercise, ExerciseCompletion, Goal, Patient


DEMO_EXERCISES = [
    # Day 1 - Gentle mobility
    {"name": "Ankle Pumps", "description": "Slowly point toes up and down to improve circulation.", "body_part": "Ankle", "sets": 3, "reps": 10, "day_number": 1, "sort_order": 1},
    {"name": "Quad Sets", "description": "Tighten thigh muscle, press knee flat into bed, hold 5 seconds.", "body_part": "Knee", "sets": 3, "reps": 10, "hold_seconds": 5, "day_number": 1, "sort_order": 2},
    {"name": "Heel Slides", "description": "Slide heel toward buttocks bending knee, then straighten.", "body_part": "Knee", "sets": 2, "reps": 10, "day_number": 1, "sort_order": 3},
    # Day 2 - Stretching
    {"name": "Hamstring Stretch", "description": "Sit on edge of bed, extend one leg, lean forward gently.", "body_part": "Hamstring", "sets": 3, "reps": 1, "hold_seconds": 30, "day_number": 2, "sort_order": 1},
    {"name": "Calf Stretch", "description": "Stand facing wall, step one foot back, press heel down.", "body_part": "Calf", "sets": 3, "reps": 1, "hold_seconds": 30, "day_number": 2, "sort_order": 2},
    {"name": "Ankle Circles", "description": "Rotate ankle clockwise then counterclockwise.", "body_part": "Ankle", "sets": 2, "reps": 10, "day_number": 2, "sort_order": 3},
    # Day 3 - Strengthening
    {"name": "Straight Leg Raises", "description": "Lie on back, tighten thigh, lift leg 12 inches, hold 5 sec.", "body_part": "Hip", "sets": 3, "reps": 10, "hold_seconds": 5, "day_number": 3, "sort_order": 1},
    {"name": "Glute Bridges", "description": "Lie on back, bend knees, squeeze glutes and lift hips.", "body_part": "Glutes", "sets": 3, "reps": 10, "day_number": 3, "sort_order": 2},
    {"name": "Standing Hip Abduction", "description": "Stand on one leg, lift other leg out to side slowly.", "body_part": "Hip", "sets": 2, "reps": 10, "day_number": 3, "sort_order": 3},
    # Day 4 - Balance
    {"name": "Single Leg Balance", "description": "Stand on one foot near counter for support, hold 30 sec.", "body_part": "Balance", "sets": 3, "reps": 1, "hold_seconds": 30, "day_number": 4, "sort_order": 1},
    {"name": "Heel-to-Toe Walk", "description": "Walk in a straight line placing heel directly in front of toes.", "body_part": "Balance", "sets": 2, "reps": 10, "day_number": 4, "sort_order": 2},
    {"name": "Quad Sets", "description": "Tighten thigh muscle, press knee flat, hold 5 seconds.", "body_part": "Knee", "sets": 3, "reps": 10, "hold_seconds": 5, "day_number": 4, "sort_order": 3},
    # Day 5 - Strength progression
    {"name": "Wall Squats", "description": "Lean back against wall, slide down to 45 degrees, hold.", "body_part": "Knee", "sets": 3, "reps": 10, "hold_seconds": 5, "day_number": 5, "sort_order": 1},
    {"name": "Calf Raises", "description": "Stand on both feet, rise up on toes, slowly lower.", "body_part": "Calf", "sets": 3, "reps": 15, "day_number": 5, "sort_order": 2},
    {"name": "Step-Ups", "description": "Step up onto a low step with one foot, then the other, step down.", "body_part": "Knee", "sets": 2, "reps": 10, "day_number": 5, "sort_order": 3},
    # Day 6 - Flexibility
    {"name": "Seated Hamstring Stretch", "description": "Sit with one leg extended, reach toward toes gently.", "body_part": "Hamstring", "sets": 3, "reps": 1, "hold_seconds": 30, "day_number": 6, "sort_order": 1},
    {"name": "Piriformis Stretch", "description": "Lie on back, cross ankle over opposite knee, pull toward chest.", "body_part": "Hip", "sets": 3, "reps": 1, "hold_seconds": 30, "day_number": 6, "sort_order": 2},
    {"name": "Ankle Pumps", "description": "Point toes up and down rhythmically.", "body_part": "Ankle", "sets": 2, "reps": 15, "day_number": 6, "sort_order": 3},
    # Day 7 - Full circuit
    {"name": "Glute Bridges", "description": "Squeeze glutes and lift hips off the floor, hold briefly.", "body_part": "Glutes", "sets": 3, "reps": 12, "day_number": 7, "sort_order": 1},
    {"name": "Wall Squats", "description": "Lean against wall and lower to 45 degrees.", "body_part": "Knee", "sets": 3, "reps": 10, "hold_seconds": 5, "day_number": 7, "sort_order": 2},
    {"name": "Calf Raises", "description": "Rise up on toes, hold 2 seconds at top, slowly lower.", "body_part": "Calf", "sets": 3, "reps": 15, "day_number": 7, "sort_order": 3},
]


async def seed_exercises(session: AsyncSession, patient_id: str) -> None:
    """Insert demo HEP exercises if patient has none."""
    result = await session.execute(
        select(Exercise).where(Exercise.patient_id == patient_id).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return

    for ex_data in DEMO_EXERCISES:
        exercise = Exercise(patient_id=patient_id, **ex_data)
        session.add(exercise)
    await session.commit()


DEMO_PATIENT_ID = "demo-patient"


async def seed_demo_patient(session: AsyncSession) -> None:
    """Create a fully-populated demo patient for showcase purposes.

    Skips if the patient already exists. Creates:
    - Patient enrolled 5 days ago, active phase
    - A recovery goal
    - All exercises seeded
    - Completion history: varied per day (3/3, 2/3, 3/3, 1/3, 2/3)
    """
    # Check if demo patient already has exercises (fully seeded)
    ex_check = await session.execute(
        select(Exercise).where(Exercise.patient_id == DEMO_PATIENT_ID).limit(1)
    )
    if ex_check.scalar_one_or_none() is not None:
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    enrollment = now - datetime.timedelta(days=4)  # 5 days in program

    # Create or update patient
    existing = await session.execute(
        select(Patient).where(Patient.patient_id == DEMO_PATIENT_ID)
    )
    patient = existing.scalar_one_or_none()
    if patient:
        patient.consent_status = True
        patient.enrollment_date = enrollment
        patient.last_message_at = now - datetime.timedelta(hours=2)
        patient.current_phase = "active"
        patient.unanswered_count = 0
    else:
        patient = Patient(
            patient_id=DEMO_PATIENT_ID,
            consent_status=True,
            enrollment_date=enrollment,
            last_message_at=now - datetime.timedelta(hours=2),
            current_phase="active",
            unanswered_count=0,
        )
        session.add(patient)

    # Deactivate any existing goals, add demo goal
    goal_check = await session.execute(
        select(Goal).where(
            Goal.patient_id == DEMO_PATIENT_ID, Goal.is_active == True
        )
    )
    for old_goal in goal_check.scalars().all():
        old_goal.is_active = False

    goal = Goal(
        patient_id=DEMO_PATIENT_ID,
        goal_text="Walk my daughter down the aisle without a cane at her wedding in June",
        is_active=True,
    )
    session.add(goal)

    await session.flush()

    for ex_data in DEMO_EXERCISES:
        exercise = Exercise(patient_id=DEMO_PATIENT_ID, **ex_data)
        session.add(exercise)
    await session.flush()

    # Fetch exercise IDs grouped by day
    result = await session.execute(
        select(Exercise)
        .where(Exercise.patient_id == DEMO_PATIENT_ID)
        .order_by(Exercise.day_number, Exercise.sort_order)
    )
    exercises = list(result.scalars().all())
    by_day = {}
    for ex in exercises:
        by_day.setdefault(ex.day_number, []).append(ex)

    today = now.date()

    # Days 1-4: varied completions (streak counts if ≥1 assigned exercise done)
    # Day 1: 3/3, Day 2: 2/3, Day 3: 3/3, Day 4: 1/3
    completions_per_day = {1: 3, 2: 2, 3: 3, 4: 1}
    for day_num in range(1, 5):
        completed_date = today - datetime.timedelta(days=5 - day_num)
        day_exercises = by_day.get(day_num, [])
        for ex in day_exercises[:completions_per_day[day_num]]:
            statuses = ["complete"] * ex.sets
            completion = ExerciseCompletion(
                patient_id=DEMO_PATIENT_ID,
                exercise_id=ex.exercise_id,
                completed_date=completed_date,
                completed_at=datetime.datetime.combine(
                    completed_date,
                    datetime.time(9, 30),
                    tzinfo=datetime.timezone.utc,
                ),
                sets_completed=ex.sets,
                set_statuses=statuses,
            )
            session.add(completion)

    # Day 5 (today): 2 out of 3 exercises completed (one with partial sets)
    day5_exercises = by_day.get(5, [])
    for i, ex in enumerate(day5_exercises[:2]):
        if i == 0:
            statuses = ["complete"] * ex.sets
        else:
            # Second exercise: mix of complete and partial
            statuses = ["complete", "partial"] + (
                ["complete"] * (ex.sets - 2) if ex.sets > 2 else []
            )
        completion = ExerciseCompletion(
            patient_id=DEMO_PATIENT_ID,
            exercise_id=ex.exercise_id,
            completed_date=today,
            completed_at=now - datetime.timedelta(minutes=45),
            sets_completed=sum(1 for s in statuses if s is not None),
            set_statuses=statuses,
            difficulty="just_right" if i == 0 else None,
        )
        session.add(completion)

    await session.commit()
