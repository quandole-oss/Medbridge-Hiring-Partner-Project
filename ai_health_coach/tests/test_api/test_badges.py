"""Tests for badge / achievement system."""
import datetime

import pytest
import pytest_asyncio

from app.db.models import Goal
from app.db.repository import (
    get_adherence_stats,
    get_completed_goal_count,
    grant_consent,
)
from app.services.badges import BADGE_CATALOG, compute_badges


# ── Pure-function unit tests ────────────────────────────────────────────────


class TestComputeBadges:
    """compute_badges is a pure function — no DB needed."""

    def _base_adherence(self, **overrides):
        base = {
            "days_in_program": 1,
            "current_day": 1,
            "total_completed": 0,
            "total_due": 3,
            "completion_rate": 0.0,
            "streak": 0,
            "milestones": {"2": False, "5": False, "7": False},
            "exercises_completed_today": 0,
            "exercises_due_today": 3,
            "daily_completions": [
                {"day": d, "completed": 0, "total": 3} for d in range(1, 8)
            ],
        }
        base.update(overrides)
        return base

    def test_no_badges_earned(self):
        badges = compute_badges(self._base_adherence(), 0, 0)
        assert len(badges) == len(BADGE_CATALOG)
        assert all(not b["earned"] for b in badges)

    def test_first_step(self):
        badges = compute_badges(self._base_adherence(total_completed=1), 0, 0)
        first = next(b for b in badges if b["id"] == "first_step")
        assert first["earned"] is True
        assert first["earned_today"] is True  # total_completed == 1

    def test_first_step_not_earned_today_when_more_than_1(self):
        badges = compute_badges(self._base_adherence(total_completed=5), 0, 0)
        first = next(b for b in badges if b["id"] == "first_step")
        assert first["earned"] is True
        assert first["earned_today"] is False

    def test_streak_badges(self):
        badges = compute_badges(self._base_adherence(streak=3), 0, 0)
        s3 = next(b for b in badges if b["id"] == "streak_3")
        s7 = next(b for b in badges if b["id"] == "streak_7")
        assert s3["earned"] is True
        assert s7["earned"] is False

        badges7 = compute_badges(self._base_adherence(streak=7), 0, 0)
        s7 = next(b for b in badges7 if b["id"] == "streak_7")
        assert s7["earned"] is True
        assert s7["earned_today"] is True

    def test_perfect_day(self):
        badges = compute_badges(
            self._base_adherence(exercises_completed_today=3, exercises_due_today=3),
            0, 0,
        )
        pd = next(b for b in badges if b["id"] == "perfect_day")
        assert pd["earned"] is True
        assert pd["earned_today"] is True

    def test_perfect_day_not_earned_when_none_due(self):
        badges = compute_badges(
            self._base_adherence(exercises_completed_today=0, exercises_due_today=0),
            0, 0,
        )
        pd = next(b for b in badges if b["id"] == "perfect_day")
        assert pd["earned"] is False

    def test_perfect_week(self):
        daily = [{"day": d, "completed": 3, "total": 3} for d in range(1, 8)]
        badges = compute_badges(
            self._base_adherence(daily_completions=daily),
            0, 0,
        )
        pw = next(b for b in badges if b["id"] == "perfect_week")
        assert pw["earned"] is True

    def test_perfect_week_not_earned_with_gap(self):
        daily = [{"day": d, "completed": 3, "total": 3} for d in range(1, 8)]
        daily[3]["completed"] = 2  # day 4 incomplete
        badges = compute_badges(
            self._base_adherence(daily_completions=daily),
            0, 0,
        )
        pw = next(b for b in badges if b["id"] == "perfect_week")
        assert pw["earned"] is False

    def test_goal_setter(self):
        badges = compute_badges(self._base_adherence(), 1, 0)
        gs = next(b for b in badges if b["id"] == "goal_setter")
        assert gs["earned"] is True

    def test_goal_crusher(self):
        badges = compute_badges(self._base_adherence(), 0, 1)
        gc = next(b for b in badges if b["id"] == "goal_crusher")
        assert gc["earned"] is True
        assert gc["earned_today"] is True

    def test_day_milestones(self):
        for day_threshold, badge_id in [(2, "day_2"), (5, "halfway"), (7, "one_week")]:
            badges = compute_badges(
                self._base_adherence(days_in_program=day_threshold), 0, 0,
            )
            b = next(x for x in badges if x["id"] == badge_id)
            assert b["earned"] is True, f"{badge_id} should be earned at day {day_threshold}"

    def test_badge_catalog_completeness(self):
        """Every badge in the catalog gets a result."""
        badges = compute_badges(self._base_adherence(), 0, 0)
        result_ids = {b["id"] for b in badges}
        catalog_ids = {b["id"] for b in BADGE_CATALOG}
        assert result_ids == catalog_ids

    def test_all_fields_present(self):
        badges = compute_badges(self._base_adherence(), 0, 0)
        for b in badges:
            assert set(b.keys()) == {"id", "name", "emoji", "description", "earned", "earned_today"}


# ── DB / Integration tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_completed_goal_count(db_session):
    """get_completed_goal_count returns count of inactive goals."""
    await grant_consent(db_session, "badge-test")

    # No completed goals yet
    count = await get_completed_goal_count(db_session, "badge-test")
    assert count == 0

    # Add an active goal
    g1 = Goal(patient_id="badge-test", goal_text="Walk 1 mile")
    db_session.add(g1)
    await db_session.commit()
    count = await get_completed_goal_count(db_session, "badge-test")
    assert count == 0  # still active

    # Deactivate (complete) it
    g1.is_active = False
    await db_session.commit()
    count = await get_completed_goal_count(db_session, "badge-test")
    assert count == 1


@pytest.mark.asyncio
async def test_adherence_endpoint_includes_badges(client, db_session, api_headers):
    """The adherence endpoint should return badges and completed_goal_count."""
    await grant_consent(db_session, "badge-ep-test")

    resp = await client.get(
        "/patients/badge-ep-test/adherence", headers=api_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "badges" in data
    assert "completed_goal_count" in data
    assert isinstance(data["badges"], list)
    assert len(data["badges"]) == len(BADGE_CATALOG)

    # Verify badge structure
    first_badge = data["badges"][0]
    assert "id" in first_badge
    assert "name" in first_badge
    assert "emoji" in first_badge
    assert "description" in first_badge
    assert "earned" in first_badge
    assert "earned_today" in first_badge
