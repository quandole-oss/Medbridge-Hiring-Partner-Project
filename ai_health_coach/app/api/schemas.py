from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CreateGoalRequest(BaseModel):
    goal_text: str
    target_date: Optional[str] = None  # ISO YYYY-MM-DD


class UpdateGoalRequest(BaseModel):
    goal_text: Optional[str] = None
    target_date: Optional[str] = None
    is_active: Optional[bool] = None


class GoalWithExercisesResponse(BaseModel):
    goal: "GoalResponse"
    exercises: List["ExerciseResponse"] = []


class ChatRequest(BaseModel):
    patient_id: str
    message: str
    idempotency_key: Optional[str] = None


class GoalResponse(BaseModel):
    goal_id: int
    goal_text: str
    target_date: Optional[str] = None
    is_active: bool
    created_at: str
    exercise_count: int = 0


class ChatResponse(BaseModel):
    patient_id: str
    response: str
    current_phase: str
    current_goal: Optional[str] = None
    goals: List[GoalResponse] = []


class EventTriggerRequest(BaseModel):
    patient_id: str
    event_type: str = Field(
        description="One of: consent_granted, program_completed, manual_phase_override"
    )
    payload: Optional[dict] = None


class EventTriggerResponse(BaseModel):
    patient_id: str
    new_phase: str
    message: str


class PatientStatusResponse(BaseModel):
    patient_id: str
    current_phase: str
    current_goal: Optional[str]
    unanswered_count: int
    last_message_at: Optional[str]
    enrollment_date: Optional[str] = None
    goals: List[GoalResponse] = []


class HealthResponse(BaseModel):
    status: str


class ExerciseResponse(BaseModel):
    exercise_id: int
    name: str
    description: Optional[str] = None
    setup_instructions: Optional[str] = None
    execution_steps: Optional[str] = None
    form_cues: Optional[str] = None
    common_mistakes: Optional[str] = None
    body_part: str
    sets: int
    reps: int
    hold_seconds: Optional[int] = None
    day_number: int
    sort_order: int
    is_completed: bool = False
    sets_completed: int = 0
    set_statuses: Optional[List[Optional[str]]] = None
    difficulty: Optional[str] = None
    feedback: Optional[str] = None
    goal_id: Optional[int] = None
    goal_text: Optional[str] = None


class ExerciseProgramResponse(BaseModel):
    patient_id: str
    day: Optional[int] = None
    exercises: List[ExerciseResponse]


class ExerciseCompleteRequest(BaseModel):
    exercise_id: int
    date: Optional[str] = Field(None, description="ISO date string, defaults to today")
    sets_completed: Optional[int] = None
    set_statuses: Optional[List[Optional[str]]] = None
    difficulty: Optional[str] = Field(
        None, description="too_easy, just_right, or too_hard"
    )
    feedback: Optional[str] = None


class ExerciseCompleteResponse(BaseModel):
    patient_id: str
    exercise_id: int
    completed: bool
    date: str
    sets_completed: int = 0
    set_statuses: Optional[List[Optional[str]]] = None
    total_sets: int = 0


class AdjustExerciseRequest(BaseModel):
    difficulty: str = Field(description="too_easy or too_hard")
    feedback: Optional[str] = None


class AdjustExerciseResponse(BaseModel):
    original_exercise: ExerciseResponse
    new_exercise: ExerciseResponse
    reasoning: str
    target_day: Optional[int] = None
    target_exercise_name: Optional[str] = None


class DailyCompletion(BaseModel):
    day: int
    completed: int
    total: int


class AdherenceResponse(BaseModel):
    patient_id: str
    days_in_program: int
    current_day: int
    total_completed: int
    total_due: int
    completion_rate: float
    streak: int
    milestones: Dict[str, bool]
    exercises_completed_today: int
    exercises_due_today: int
    daily_completions: List[DailyCompletion]


# ── PRO (Patient-Reported Outcomes) ──────────────────────────────────────────


class OutcomeReportRequest(BaseModel):
    pain_score: int = Field(ge=0, le=10)
    function_score: int = Field(ge=0, le=10)
    wellbeing_score: int = Field(ge=0, le=10)
    notes: Optional[str] = None


class OutcomeReportResponse(BaseModel):
    report_id: int
    patient_id: str
    report_date: str
    pain_score: int
    function_score: int
    wellbeing_score: int
    notes: Optional[str]


class OutcomeSummaryResponse(BaseModel):
    patient_id: str
    latest: Optional[OutcomeReportResponse]
    pain_trend: str
    function_trend: str
    wellbeing_trend: str
    report_count: int
    reports: List[OutcomeReportResponse]


# ── Education Content ────────────────────────────────────────────────────────


class EducationContentResponse(BaseModel):
    content_id: int
    title: str
    body: str
    content_type: str
    body_part: Optional[str]
    is_viewed: bool = False


# ── Progressive Pathways ─────────────────────────────────────────────────────


class PathwayStatusResponse(BaseModel):
    patient_id: str
    pathway_name: Optional[str]
    current_week: int
    total_weeks: int
    week_theme: str
    advancement_threshold: float
    current_adherence: float
    can_advance: bool
    blocker: Optional[str]


class PathwayAdvanceResponse(BaseModel):
    advanced: bool
    new_week: int
    reason: str
