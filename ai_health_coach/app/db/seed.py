import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    EducationContent,
    Exercise,
    ExerciseCompletion,
    Goal,
    OutcomeReport,
    Patient,
    Pathway,
    PathwayWeek,
)


DEMO_EXERCISES = [
    # ── Day 1 · Gentle Mobility ──────────────────────────────────────────────
    {
        "name": "Ankle Pumps",
        "body_part": "Ankle",
        "sets": 3, "reps": 10,
        "day_number": 1, "sort_order": 1,
        "setup_instructions": "Lie flat on your back or sit upright in bed with your legs extended and relaxed.",
        "execution_steps": "Slowly pull your toes up toward your shin as far as comfortable, then point them away from you. Each up-and-down movement counts as one repetition.",
        "form_cues": "Move only at the ankle — keep your knee still. Breathe steadily throughout.",
        "common_mistakes": "Bending the knee during the movement. Moving too fast — slow, controlled pumps are more effective for circulation.",
    },
    {
        "name": "Quad Sets",
        "body_part": "Knee",
        "sets": 3, "reps": 10, "hold_seconds": 5,
        "day_number": 1, "sort_order": 2,
        "setup_instructions": "Lie flat on your back with your legs straight. Place a small rolled towel under the knee you are exercising.",
        "execution_steps": "Tighten the muscle on the top of your thigh (quadriceps) by pressing the back of your knee firmly down into the towel. Hold for 5 seconds, then fully relax.",
        "form_cues": "You should feel the thigh muscle tighten but your leg should not lift off the bed. Keep the opposite leg relaxed.",
        "common_mistakes": "Holding your breath during the contraction. Lifting the heel off the bed instead of pressing the knee down.",
    },
    {
        "name": "Heel Slides",
        "body_part": "Knee",
        "sets": 2, "reps": 10,
        "day_number": 1, "sort_order": 3,
        "setup_instructions": "Lie flat on your back with both legs straight. Keep your heel in contact with the bed surface throughout.",
        "execution_steps": "Slowly slide your heel toward your buttocks by bending your knee as far as comfortable. Pause briefly, then slowly slide it back to the starting position.",
        "form_cues": "Keep the movement smooth and controlled. Only go as far as your comfort allows — do not force the range of motion.",
        "common_mistakes": "Lifting the heel off the bed instead of sliding it. Rushing through the movement — a slow return is just as important as the bend.",
    },
    # ── Day 2 · Stretching ───────────────────────────────────────────────────
    {
        "name": "Hamstring Stretch",
        "body_part": "Hamstring",
        "sets": 3, "reps": 1, "hold_seconds": 30,
        "day_number": 2, "sort_order": 1,
        "setup_instructions": "Sit on the edge of a firm chair or bed. Extend the leg to be stretched straight out in front of you with your heel resting on the floor.",
        "execution_steps": "Sit tall, then hinge forward slowly from your hips — not your waist — until you feel a gentle pull along the back of your thigh. Hold for 30 seconds, then sit back upright.",
        "form_cues": "Keep your back straight throughout the lean. The stretch should feel like mild tension, never sharp pain.",
        "common_mistakes": "Rounding the lower back instead of hinging at the hip. Bouncing into the stretch — hold it still.",
    },
    {
        "name": "Calf Stretch",
        "body_part": "Calf",
        "sets": 3, "reps": 1, "hold_seconds": 30,
        "day_number": 2, "sort_order": 2,
        "setup_instructions": "Stand facing a wall with both hands resting on it for support. Place the foot to be stretched one large step behind you.",
        "execution_steps": "Keep the back knee straight and the back heel flat on the floor. Gently lean your hips toward the wall until you feel a stretch in the calf of the back leg. Hold for 30 seconds.",
        "form_cues": "Both feet should point straight ahead. Keep your back heel pressed firmly into the floor throughout the hold.",
        "common_mistakes": "Allowing the back heel to lift off the floor. Bending the back knee, which reduces the stretch.",
    },
    {
        "name": "Ankle Circles",
        "body_part": "Ankle",
        "sets": 2, "reps": 10,
        "day_number": 2, "sort_order": 3,
        "setup_instructions": "Sit in a chair or lie on your back with your leg slightly elevated so the foot can move freely.",
        "execution_steps": "Slowly rotate your foot in a full circle — 10 circles clockwise, then 10 circles counterclockwise. Keep the movement large and controlled.",
        "form_cues": "Move only at the ankle joint. Try to trace as large a circle as possible to maximize range of motion.",
        "common_mistakes": "Moving the entire leg instead of isolating the ankle. Making small, rushed circles instead of slow, full-range ones.",
    },
    # ── Day 3 · Strengthening ────────────────────────────────────────────────
    {
        "name": "Straight Leg Raises",
        "body_part": "Hip",
        "sets": 3, "reps": 10, "hold_seconds": 5,
        "day_number": 3, "sort_order": 1,
        "setup_instructions": "Lie flat on your back. Bend the uninvolved knee with that foot flat on the bed. Keep the leg you are exercising straight.",
        "execution_steps": "Tighten the thigh of the straight leg, then lift it until it is level with the opposite bent knee (about 12 inches off the bed). Hold 5 seconds, then slowly lower.",
        "form_cues": "Tighten the thigh before lifting — this protects the knee. Keep your lower back flat against the bed throughout.",
        "common_mistakes": "Letting the lower back arch away from the bed as the leg rises. Bending the knee of the lifting leg.",
    },
    {
        "name": "Glute Bridges",
        "body_part": "Glutes",
        "sets": 3, "reps": 10,
        "day_number": 3, "sort_order": 2,
        "setup_instructions": "Lie flat on your back with your knees bent and feet flat on the floor, hip-width apart. Rest your arms at your sides.",
        "execution_steps": "Squeeze your glutes and push through your heels to lift your hips off the floor until your body forms a straight line from shoulders to knees. Hold 2 seconds at the top, then slowly lower.",
        "form_cues": "Drive through the heels, not the toes. Keep your core gently braced and avoid overarching your lower back at the top.",
        "common_mistakes": "Pushing through the toes instead of the heels. Letting the knees fall inward during the lift.",
    },
    {
        "name": "Standing Hip Abduction",
        "body_part": "Hip",
        "sets": 2, "reps": 10,
        "day_number": 3, "sort_order": 3,
        "setup_instructions": "Stand upright next to a counter or sturdy chair and hold it lightly for balance. Shift your weight onto your support leg.",
        "execution_steps": "Keeping your toes pointing forward and your trunk upright, slowly lift the outside leg out to the side to about 30–45 degrees. Pause, then slowly lower it back.",
        "form_cues": "Do not lean your torso to the side as the leg rises — the movement comes entirely from the hip. Keep the moving foot flexed.",
        "common_mistakes": "Leaning the body sideways to compensate for limited range. Rotating the hip outward so the toe points toward the ceiling.",
    },
    # ── Day 4 · Balance ──────────────────────────────────────────────────────
    {
        "name": "Single Leg Balance",
        "body_part": "Balance",
        "sets": 3, "reps": 1, "hold_seconds": 30,
        "day_number": 4, "sort_order": 1,
        "setup_instructions": "Stand next to a counter or sturdy chair with one hand lightly resting on it for safety. Stand with feet hip-width apart.",
        "execution_steps": "Shift your weight onto one foot and slowly lift the other foot just off the floor. Hold for 30 seconds, then switch sides. Try to use the support as little as possible.",
        "form_cues": "Keep a soft bend in the standing knee — do not lock it out. Focus your gaze on a fixed point ahead to help with balance.",
        "common_mistakes": "Gripping the counter tightly instead of using it only for safety. Locking the standing knee straight.",
    },
    {
        "name": "Heel-to-Toe Walk",
        "body_part": "Balance",
        "sets": 2, "reps": 10,
        "day_number": 4, "sort_order": 2,
        "setup_instructions": "Stand at one end of a clear hallway or near a wall for safety. Place your feet together to start.",
        "execution_steps": "Step forward, placing the heel of your front foot directly in front of the toes of your back foot. Continue for 10 steps, then turn and walk back.",
        "form_cues": "Look straight ahead, not down at your feet. Walk slowly and deliberately — accuracy matters more than speed.",
        "common_mistakes": "Placing the foot to the side instead of directly in front. Rushing the steps, which reduces the balance challenge.",
    },
    {
        "name": "Quad Sets",
        "body_part": "Knee",
        "sets": 3, "reps": 10, "hold_seconds": 5,
        "day_number": 4, "sort_order": 3,
        "setup_instructions": "Lie flat on your back with your legs straight. Place a small rolled towel under the knee you are exercising.",
        "execution_steps": "Tighten the muscle on the top of your thigh by pressing the back of your knee firmly down into the towel. Hold for 5 seconds, then fully relax.",
        "form_cues": "You should feel the thigh muscle tighten but your leg should not lift off the bed. Keep the opposite leg relaxed.",
        "common_mistakes": "Holding your breath during the contraction. Lifting the heel off the bed instead of pressing the knee down.",
    },
    # ── Day 5 · Strength Progression ────────────────────────────────────────
    {
        "name": "Wall Squats",
        "body_part": "Knee",
        "sets": 3, "reps": 10, "hold_seconds": 5,
        "day_number": 5, "sort_order": 1,
        "setup_instructions": "Stand with your back flat against a smooth wall. Walk your feet out about 18 inches from the wall, hip-width apart.",
        "execution_steps": "Slowly slide your back down the wall until your knees are at roughly a 45-degree angle (or as far as comfortable). Hold for 5 seconds, then slide back up.",
        "form_cues": "Keep your knees aligned over your second toe — do not let them cave inward. Your back should remain in full contact with the wall throughout.",
        "common_mistakes": "Letting the knees drift forward past the toes. Sliding down too far too soon — start shallow and increase depth gradually.",
    },
    {
        "name": "Calf Raises",
        "body_part": "Calf",
        "sets": 3, "reps": 15,
        "day_number": 5, "sort_order": 2,
        "setup_instructions": "Stand upright with feet hip-width apart, holding a counter or chair back lightly for balance.",
        "execution_steps": "Rise up onto the balls of both feet as high as possible, hold for 2 seconds at the top, then slowly lower your heels back to the floor.",
        "form_cues": "Rise evenly through both feet. Lower slowly — the controlled descent builds as much strength as the rise.",
        "common_mistakes": "Rolling to the outside of the feet when rising. Dropping the heels quickly instead of lowering with control.",
    },
    {
        "name": "Step-Ups",
        "body_part": "Knee",
        "sets": 2, "reps": 10,
        "day_number": 5, "sort_order": 3,
        "setup_instructions": "Stand in front of a low, stable step (4–6 inches high). Hold a railing or wall for support if needed.",
        "execution_steps": "Place your entire foot on the step, then push through that heel to step up, bringing the other foot up beside it. Step back down one foot at a time. Alternate the leading foot each set.",
        "form_cues": "Push through the heel of the stepping foot, not the toes. Keep your trunk upright — do not lean forward excessively.",
        "common_mistakes": "Pushing off the back foot to help get up — the work should come entirely from the stepping leg. Letting the knee cave inward on the step-up.",
    },
    # ── Day 6 · Flexibility ──────────────────────────────────────────────────
    {
        "name": "Seated Hamstring Stretch",
        "body_part": "Hamstring",
        "sets": 3, "reps": 1, "hold_seconds": 30,
        "day_number": 6, "sort_order": 1,
        "setup_instructions": "Sit near the edge of a firm chair. Extend one leg straight out with your heel on the floor and your toes pointing up.",
        "execution_steps": "Sitting tall, hinge forward from your hips until you feel a gentle stretch along the back of the extended thigh. Hold for 30 seconds, then return upright and switch legs.",
        "form_cues": "Keep your spine long — do not round your back. The stretch is felt in the thigh, not the lower back.",
        "common_mistakes": "Rounding the spine forward instead of hinging at the hip. Locking the knee so hard the leg shakes — a soft knee lock is fine.",
    },
    {
        "name": "Piriformis Stretch",
        "body_part": "Hip",
        "sets": 3, "reps": 1, "hold_seconds": 30,
        "day_number": 6, "sort_order": 2,
        "setup_instructions": "Lie flat on your back with both knees bent and feet flat on the floor.",
        "execution_steps": "Cross the ankle of the leg to be stretched over the opposite knee, forming a figure-4 shape. Gently pull the uncrossed thigh toward your chest until you feel a deep stretch in the crossed hip and buttock. Hold for 30 seconds.",
        "form_cues": "Keep your head and shoulders relaxed on the floor. Flex the foot of the crossed leg to protect the knee joint.",
        "common_mistakes": "Letting the lower back lift off the floor. Pulling too aggressively — the stretch should be deep but never painful.",
    },
    {
        "name": "Ankle Pumps",
        "body_part": "Ankle",
        "sets": 2, "reps": 15,
        "day_number": 6, "sort_order": 3,
        "setup_instructions": "Lie flat on your back or sit upright with your legs extended and relaxed.",
        "execution_steps": "Pull your toes up toward your shin, then point them away. Perform at a steady, rhythmic pace for 15 repetitions.",
        "form_cues": "Move only at the ankle — keep your knee still. Breathe steadily throughout.",
        "common_mistakes": "Bending the knee during the movement. Moving too fast — steady pumps are more effective for circulation.",
    },
    # ── Day 7 · Full Circuit ─────────────────────────────────────────────────
    {
        "name": "Glute Bridges",
        "body_part": "Glutes",
        "sets": 3, "reps": 12,
        "day_number": 7, "sort_order": 1,
        "setup_instructions": "Lie flat on your back with knees bent, feet flat on the floor hip-width apart, arms relaxed at your sides.",
        "execution_steps": "Squeeze your glutes and push through your heels to lift your hips until your body forms a straight line from shoulders to knees. Hold 2 seconds, then slowly lower.",
        "form_cues": "Drive through the heels. Keep your core braced and avoid overarching the lower back at the top position.",
        "common_mistakes": "Pushing through the toes instead of the heels. Letting the knees fall inward during the lift.",
    },
    {
        "name": "Wall Squats",
        "body_part": "Knee",
        "sets": 3, "reps": 10, "hold_seconds": 5,
        "day_number": 7, "sort_order": 2,
        "setup_instructions": "Stand with your back flat against a smooth wall, feet about 18 inches out, hip-width apart.",
        "execution_steps": "Slide your back down the wall to a 45-degree knee angle, hold for 5 seconds, then slide back up.",
        "form_cues": "Knees stay aligned over the second toe. Back maintains full contact with the wall.",
        "common_mistakes": "Knees drifting inward. Sliding down too far before you have built sufficient strength.",
    },
    {
        "name": "Calf Raises",
        "body_part": "Calf",
        "sets": 3, "reps": 15,
        "day_number": 7, "sort_order": 3,
        "setup_instructions": "Stand upright with feet hip-width apart, holding a counter lightly for balance.",
        "execution_steps": "Rise onto the balls of both feet, hold 2 seconds at the top, then slowly lower your heels back to the floor.",
        "form_cues": "Rise evenly through both feet. Lower slowly — the controlled descent is as important as the rise.",
        "common_mistakes": "Rolling to the outside of the feet. Dropping the heels quickly instead of lowering with control.",
    },
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
        target_date=(now + datetime.timedelta(days=90)).date(),
        is_active=True,
    )
    session.add(goal)

    await session.flush()

    # ── Create 4-week pathway ──
    pathway_check = await session.execute(
        select(Pathway).where(Pathway.name == "Post-Op Knee Recovery").limit(1)
    )
    pathway = pathway_check.scalar_one_or_none()
    if not pathway:
        pathway = Pathway(
            name="Post-Op Knee Recovery",
            description="A progressive 4-week program for post-operative knee rehabilitation, advancing through foundation, building, strengthening, and integration phases.",
            total_weeks=4,
            condition="knee",
            is_active=True,
        )
        session.add(pathway)
        await session.flush()

        weeks_data = [
            (1, "Foundation", 0.8, None),
            (2, "Building", 0.7, 6),
            (3, "Strengthening", 0.75, 5),
            (4, "Integration", 0.8, 4),
        ]
        for wn, theme, threshold, pain_ceil in weeks_data:
            pw = PathwayWeek(
                pathway_id=pathway.pathway_id,
                week_number=wn,
                theme=theme,
                advancement_threshold=threshold,
                pain_ceiling=pain_ceil,
            )
            session.add(pw)
        await session.flush()

    patient.pathway_id = pathway.pathway_id
    patient.current_week = 1

    for ex_data in DEMO_EXERCISES:
        exercise = Exercise(patient_id=DEMO_PATIENT_ID, week_number=1, **ex_data)
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

    # ── PRO outcome reports: realistic recovery arc ──
    pro_data = [
        # (days_ago, pain, function, wellbeing)
        (4, 7, 3, 4),
        (3, 6, 4, 5),
        (2, 6, 4, 5),
        (1, 5, 5, 6),
        (0, 4, 6, 6),
    ]
    for days_ago, pain, func, well in pro_data:
        report_date = today - datetime.timedelta(days=days_ago)
        report = OutcomeReport(
            patient_id=DEMO_PATIENT_ID,
            report_date=report_date,
            pain_score=pain,
            function_score=func,
            wellbeing_score=well,
            created_at=datetime.datetime.combine(
                report_date,
                datetime.time(8, 0),
                tzinfo=datetime.timezone.utc,
            ),
        )
        session.add(report)

    await session.commit()


EDUCATION_ITEMS = [
    # Day 1 — mobility
    {
        "title": "Why ankle mobility matters after surgery",
        "body": "After knee or lower-extremity surgery, ankle mobility is one of the first things to address. Gentle ankle pumps help restore blood flow, reduce swelling, and prevent blood clots. Even small movements signal your nervous system that the limb is safe to use, which accelerates the healing cascade. Aim for slow, full-range pumps rather than quick, shallow ones.",
        "content_type": "article",
        "body_part": "Ankle",
        "day_theme": "mobility",
        "sort_order": 1,
    },
    {
        "title": "3 signs your quad set is working",
        "body": "A proper quad set should: (1) make the muscle on top of your thigh visibly tighten, (2) press the back of your knee firmly into the towel or bed, and (3) cause your kneecap to glide slightly upward. If you can see and feel all three, you are activating correctly. If not, try placing your fingers on the inner quad just above the knee to check for contraction.",
        "content_type": "tip",
        "body_part": "Knee",
        "day_theme": "mobility",
        "sort_order": 2,
    },
    # Day 2 — stretching
    {
        "title": "Is it normal to feel stiff in the morning?",
        "body": "Yes — morning stiffness is very common during recovery. Overnight, your joints lose some of the lubricating fluid that movement provides. Gentle stretching within the first 30 minutes of waking up helps restore that fluid and signals your muscles to relax. Stiffness that lasts more than an hour or worsens over several days should be mentioned to your physical therapist.",
        "content_type": "faq",
        "body_part": "Hamstring",
        "day_theme": "stretching",
        "sort_order": 1,
    },
    {
        "title": "The difference between stretching pain and injury pain",
        "body": "A good stretch feels like mild tension or a gentle pull — it should be uncomfortable but never sharp. Injury pain tends to be sudden, localized, and may come with swelling or instability. If stretching produces a sharp or burning sensation, stop immediately and let your PT know. The 'no pain, no gain' philosophy does not apply to rehabilitation.",
        "content_type": "article",
        "body_part": "Calf",
        "day_theme": "stretching",
        "sort_order": 2,
    },
    # Day 3 — strengthening
    {
        "title": "How strengthening exercises rebuild after surgery",
        "body": "After surgery, muscles lose strength quickly — sometimes 10–15% per week of inactivity. Strengthening exercises like straight leg raises and glute bridges reverse this process by creating micro-stress on muscle fibers, which triggers your body to repair them stronger than before. Start with bodyweight only and progress gradually as your PT advises.",
        "content_type": "article",
        "body_part": "Hip",
        "day_theme": "strengthening",
        "sort_order": 1,
    },
    {
        "title": "Why glute activation matters for knee recovery",
        "body": "Weak glutes are one of the most common contributors to knee pain and instability. Your gluteus medius controls hip stability during walking, and when it is weak, the knee compensates by collapsing inward. Exercises like glute bridges and hip abduction directly target this muscle, protecting your knee during daily activities.",
        "content_type": "tip",
        "body_part": "Glutes",
        "day_theme": "strengthening",
        "sort_order": 2,
    },
    # Day 4 — balance
    {
        "title": "Understanding balance and fall prevention",
        "body": "Balance is a skill, not just a physical attribute. It relies on three systems working together: your vision, your inner ear (vestibular system), and proprioceptors in your joints and muscles. After surgery, the proprioceptors in the affected joint need retraining. Single-leg stands and heel-to-toe walks challenge these sensors in a safe, progressive way.",
        "content_type": "article",
        "body_part": "Balance",
        "day_theme": "balance",
        "sort_order": 1,
    },
    {
        "title": "Why balance training feels harder some days",
        "body": "Balance performance varies day to day based on fatigue, hydration, sleep quality, and even stress levels. If balance exercises feel unusually difficult, it does not mean you are regressing — it means your body is processing a lot. Keep practicing, and your baseline will steadily improve over weeks.",
        "content_type": "faq",
        "body_part": "Balance",
        "day_theme": "balance",
        "sort_order": 2,
    },
    # Day 5 — strength_progression
    {
        "title": "Progressive overload: when to push harder",
        "body": "Progressive overload means gradually increasing the difficulty of your exercises over time. In PT, this might mean adding reps, increasing hold time, or moving to a harder variation. The right time to progress is when your current exercises feel manageable with good form for two consecutive sessions. Never increase more than one variable at a time.",
        "content_type": "article",
        "body_part": "Knee",
        "day_theme": "strength_progression",
        "sort_order": 1,
    },
    {
        "title": "Wall squats vs. free squats: which is right for you?",
        "body": "Wall squats provide back support and limit your range of motion, making them ideal for early-stage recovery. Free squats require more balance and core control. Your PT will transition you from wall squats to free squats when your quadriceps and glutes are strong enough to maintain proper form without support. Do not rush this transition.",
        "content_type": "tip",
        "body_part": "Knee",
        "day_theme": "strength_progression",
        "sort_order": 2,
    },
    # Day 6 — flexibility
    {
        "title": "Flexibility vs. mobility: what is the difference?",
        "body": "Flexibility refers to how far a muscle can stretch passively (like touching your toes). Mobility refers to how well a joint moves through its full range under control. Both matter in recovery. Stretching improves flexibility, while controlled movement exercises improve mobility. Your program includes both because they complement each other.",
        "content_type": "article",
        "body_part": "Hamstring",
        "day_theme": "flexibility",
        "sort_order": 1,
    },
    {
        "title": "The piriformis: a small muscle with big impact",
        "body": "The piriformis is a deep hip rotator muscle that sits near the sciatic nerve. When tight, it can cause hip and buttock pain and sometimes radiating discomfort down the leg. The figure-4 stretch directly targets this muscle. Hold the stretch gently — forcing it can irritate the sciatic nerve rather than relieve tension.",
        "content_type": "tip",
        "body_part": "Hip",
        "day_theme": "flexibility",
        "sort_order": 2,
    },
    # Day 7 — full_circuit
    {
        "title": "Why circuit-style workouts help recovery",
        "body": "Circuit workouts combine multiple exercises with minimal rest, which builds muscular endurance and cardiovascular conditioning simultaneously. In rehabilitation, circuits mimic the demands of daily life — where you do not rest between walking to the kitchen, bending to pick something up, and climbing stairs. Think of Day 7 as a rehearsal for real-world movement.",
        "content_type": "article",
        "body_part": "Knee",
        "day_theme": "full_circuit",
        "sort_order": 1,
    },
    {
        "title": "How to pace yourself during a full circuit",
        "body": "Listen to your body between exercises. A brief rest of 30–60 seconds is fine and expected. If you feel sharp pain or significant fatigue in any exercise, reduce the reps or skip that exercise for the day and let your PT know. Completing the circuit with good form is more important than finishing quickly.",
        "content_type": "tip",
        "body_part": "Glutes",
        "day_theme": "full_circuit",
        "sort_order": 2,
    },
]


async def seed_education_content(session: AsyncSession) -> None:
    """Insert education content if none exists."""
    result = await session.execute(
        select(EducationContent).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return

    for item in EDUCATION_ITEMS:
        content = EducationContent(**item, is_active=True)
        session.add(content)
    await session.commit()
