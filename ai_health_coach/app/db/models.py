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

    goals: Mapped[List["Goal"]] = relationship(back_populates="patient")
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="patient")
    exercises: Mapped[List["Exercise"]] = relationship(back_populates="patient")
    exercise_completions: Mapped[List["ExerciseCompletion"]] = relationship(
        back_populates="patient"
    )


class Goal(Base):
    __tablename__ = "goals"

    goal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(String, ForeignKey("patients.patient_id"))
    goal_text: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    patient: Mapped["Patient"] = relationship(back_populates="goals")


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
    description: Mapped[str] = mapped_column(String)
    body_part: Mapped[str] = mapped_column(String)
    sets: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    hold_seconds: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    day_number: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    replaced_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("exercises.exercise_id"), default=None
    )

    patient: Mapped["Patient"] = relationship(back_populates="exercises")


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
