import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Pathway(Base):
    __tablename__ = "pathways"

    pathway_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    total_weeks: Mapped[int] = mapped_column(Integer)
    condition: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    weeks: Mapped[List["PathwayWeek"]] = relationship(back_populates="pathway")


class PathwayWeek(Base):
    __tablename__ = "pathway_weeks"

    week_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    pathway_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pathways.pathway_id")
    )
    week_number: Mapped[int] = mapped_column(Integer)
    theme: Mapped[str] = mapped_column(String)
    advancement_threshold: Mapped[float] = mapped_column(default=0.7)
    pain_ceiling: Mapped[Optional[int]] = mapped_column(Integer, default=None)

    pathway: Mapped["Pathway"] = relationship(back_populates="weeks")


class Patient(Base):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(String, primary_key=True)
    consent_status: Mapped[bool] = mapped_column(Boolean, default=False)
    enrollment_date: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, default=None
    )
    last_message_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, default=None
    )
    current_phase: Mapped[str] = mapped_column(String, default="pending")
    unanswered_count: Mapped[int] = mapped_column(Integer, default=0)
    pathway_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("pathways.pathway_id"), default=None
    )
    current_week: Mapped[int] = mapped_column(Integer, default=1)

    goals: Mapped[List["Goal"]] = relationship(back_populates="patient")
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="patient")
    exercises: Mapped[List["Exercise"]] = relationship(back_populates="patient")
    exercise_completions: Mapped[List["ExerciseCompletion"]] = relationship(
        back_populates="patient"
    )
    outcome_reports: Mapped[List["OutcomeReport"]] = relationship(
        back_populates="patient"
    )
    insights: Mapped[List["PatientInsight"]] = relationship(
        back_populates="patient"
    )
    alerts: Mapped[List["ClinicalAlert"]] = relationship(back_populates="patient")


class Goal(Base):
    __tablename__ = "goals"

    goal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(String, ForeignKey("patients.patient_id"))
    goal_text: Mapped[str] = mapped_column(String)
    target_date: Mapped[Optional[datetime.date]] = mapped_column(Date, default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    patient: Mapped["Patient"] = relationship(back_populates="goals")
    exercises: Mapped[List["Exercise"]] = relationship("Exercise", back_populates="goal")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(String, ForeignKey("patients.patient_id"))
    event_type: Mapped[str] = mapped_column(String)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    patient: Mapped["Patient"] = relationship(back_populates="audit_logs")


class Exercise(Base):
    __tablename__ = "exercises"

    exercise_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id")
    )
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, default=None)
    setup_instructions: Mapped[Optional[str]] = mapped_column(String, default=None)
    execution_steps: Mapped[Optional[str]] = mapped_column(String, default=None)
    form_cues: Mapped[Optional[str]] = mapped_column(String, default=None)
    common_mistakes: Mapped[Optional[str]] = mapped_column(String, default=None)
    body_part: Mapped[str] = mapped_column(String)
    sets: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    hold_seconds: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    day_number: Mapped[int] = mapped_column(Integer)
    week_number: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    replaced_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("exercises.exercise_id"), default=None
    )
    goal_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("goals.goal_id"), default=None
    )

    patient: Mapped["Patient"] = relationship(back_populates="exercises")
    goal: Mapped[Optional["Goal"]] = relationship("Goal", back_populates="exercises")


class ExerciseCompletion(Base):
    __tablename__ = "exercise_completions"
    __table_args__ = (
        UniqueConstraint(
            "patient_id", "exercise_id", "completed_date",
            name="uq_completion_per_day",
        ),
    )

    completion_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id")
    )
    exercise_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exercises.exercise_id")
    )
    completed_date: Mapped[datetime.date] = mapped_column(Date)
    completed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    sets_completed: Mapped[int] = mapped_column(Integer, default=0)
    set_statuses: Mapped[Optional[list]] = mapped_column(JSON, default=None)
    difficulty: Mapped[Optional[str]] = mapped_column(String, default=None)
    feedback: Mapped[Optional[str]] = mapped_column(String, default=None)

    patient: Mapped["Patient"] = relationship(back_populates="exercise_completions")


class OutcomeReport(Base):
    __tablename__ = "outcome_reports"

    report_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id")
    )
    report_date: Mapped[datetime.date] = mapped_column(Date)
    pain_score: Mapped[int] = mapped_column(Integer)
    function_score: Mapped[int] = mapped_column(Integer)
    wellbeing_score: Mapped[int] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(String, default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    patient: Mapped["Patient"] = relationship(back_populates="outcome_reports")


class PatientInsight(Base):
    __tablename__ = "patient_insights"

    insight_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id")
    )
    category: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(default=0.7)
    times_reinforced: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    last_reinforced_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    patient: Mapped["Patient"] = relationship(back_populates="insights")


class DailyBriefing(Base):
    __tablename__ = "daily_briefings"
    __table_args__ = (
        UniqueConstraint("patient_id", "briefing_date", name="uq_briefing_per_day"),
    )

    briefing_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id")
    )
    briefing_date: Mapped[datetime.date] = mapped_column(Date)
    message: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class ClinicianPatientSummary(Base):
    __tablename__ = "clinician_patient_summaries"
    __table_args__ = (
        UniqueConstraint(
            "patient_id", "summary_date", name="uq_patient_summary_per_day"
        ),
    )

    summary_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id")
    )
    summary_date: Mapped[datetime.date] = mapped_column(Date)
    summary_text: Mapped[str] = mapped_column(String)
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String)
    risk_explanation: Mapped[str] = mapped_column(String)
    risk_factors: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class CaseloadBriefing(Base):
    __tablename__ = "caseload_briefings"
    __table_args__ = (
        UniqueConstraint(
            "clinician_id", "briefing_date", name="uq_caseload_per_day"
        ),
    )

    briefing_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    clinician_id: Mapped[str] = mapped_column(
        String, ForeignKey("clinicians.clinician_id")
    )
    briefing_date: Mapped[datetime.date] = mapped_column(Date)
    briefing_text: Mapped[str] = mapped_column(String)
    patient_count: Mapped[int] = mapped_column(Integer)
    high_risk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class Clinician(Base):
    __tablename__ = "clinicians"

    clinician_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True)
    api_key: Mapped[str] = mapped_column(String, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class ClinicalAlert(Base):
    __tablename__ = "clinical_alerts"

    alert_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id")
    )
    alert_type: Mapped[str] = mapped_column(String)
    urgency: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")
    context: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    acknowledged_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, default=None
    )
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, default=None
    )
    resolved_note: Mapped[Optional[str]] = mapped_column(String, default=None)

    patient: Mapped["Patient"] = relationship(back_populates="alerts")


class EducationContent(Base):
    __tablename__ = "education_content"

    content_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String)  # article, tip, faq
    body_part: Mapped[Optional[str]] = mapped_column(String, default=None)
    day_theme: Mapped[Optional[str]] = mapped_column(String, default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EducationView(Base):
    __tablename__ = "education_views"

    view_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.patient_id")
    )
    content_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("education_content.content_id")
    )
    viewed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
