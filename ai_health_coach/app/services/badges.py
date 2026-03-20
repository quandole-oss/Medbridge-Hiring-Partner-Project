"""Badge / achievement computation — pure functions, no DB access."""

from typing import List


BADGE_CATALOG = [
    {
        "id": "first_step",
        "name": "First Step",
        "emoji": "\U0001f45f",
        "description": "Complete your first exercise",
    },
    {
        "id": "streak_3",
        "name": "On Fire",
        "emoji": "\U0001f525",
        "description": "Achieve a 3-day streak",
    },
    {
        "id": "streak_7",
        "name": "Week Warrior",
        "emoji": "\u26a1",
        "description": "Achieve a 7-day streak",
    },
    {
        "id": "perfect_day",
        "name": "Perfect Day",
        "emoji": "\u2b50",
        "description": "Complete all exercises in a day",
    },
    {
        "id": "perfect_week",
        "name": "Perfect Week",
        "emoji": "\U0001f3c6",
        "description": "Complete every exercise all 7 days",
    },
    {
        "id": "goal_setter",
        "name": "Goal Setter",
        "emoji": "\U0001f3af",
        "description": "Set your first recovery goal",
    },
    {
        "id": "goal_crusher",
        "name": "Goal Crusher",
        "emoji": "\U0001f4aa",
        "description": "Complete a recovery goal",
    },
    {
        "id": "day_2",
        "name": "Getting Started",
        "emoji": "\U0001f331",
        "description": "Reach Day 2 of your program",
    },
    {
        "id": "halfway",
        "name": "Halfway There",
        "emoji": "\U0001f680",
        "description": "Reach Day 5 of your program",
    },
    {
        "id": "one_week",
        "name": "One Week Strong",
        "emoji": "\U0001f389",
        "description": "Complete a full week",
    },
]


def compute_badges(
    adherence: dict,
    active_goal_count: int,
    completed_goal_count: int,
) -> List[dict]:
    """Pure function: return list of badge dicts with earned / earned_today flags.

    ``adherence`` is the dict returned by ``get_adherence_stats``.
    """
    total_completed = adherence.get("total_completed", 0)
    streak = adherence.get("streak", 0)
    days_in_program = adherence.get("days_in_program", 0)
    exercises_completed_today = adherence.get("exercises_completed_today", 0)
    exercises_due_today = adherence.get("exercises_due_today", 0)
    daily_completions = adherence.get("daily_completions", [])

    # Perfect-day: all exercises done today and at least 1 due
    perfect_day = (
        exercises_due_today > 0
        and exercises_completed_today == exercises_due_today
    )

    # Perfect-week: every day (1-7) has completed == total and total > 0
    perfect_week = (
        len(daily_completions) == 7
        and all(
            dc["total"] > 0 and dc["completed"] == dc["total"]
            for dc in daily_completions
        )
    )

    conditions = {
        "first_step": total_completed >= 1,
        "streak_3": streak >= 3,
        "streak_7": streak >= 7,
        "perfect_day": perfect_day,
        "perfect_week": perfect_week,
        "goal_setter": active_goal_count >= 1,
        "goal_crusher": completed_goal_count >= 1,
        "day_2": days_in_program >= 2,
        "halfway": days_in_program >= 5,
        "one_week": days_in_program >= 7,
    }

    # Heuristics for "just earned" — helps the UI decide whether to celebrate
    earned_today_hints = {
        "first_step": total_completed == 1,
        "streak_3": streak == 3,
        "streak_7": streak == 7,
        "perfect_day": True,  # ephemeral — always celebrate when earned
        "perfect_week": True,
        "goal_setter": active_goal_count == 1,
        "goal_crusher": completed_goal_count == 1,
        "day_2": days_in_program == 2,
        "halfway": days_in_program == 5,
        "one_week": days_in_program == 7,
    }

    badges = []
    for badge in BADGE_CATALOG:
        bid = badge["id"]
        earned = conditions.get(bid, False)
        badges.append({
            "id": bid,
            "name": badge["name"],
            "emoji": badge["emoji"],
            "description": badge["description"],
            "earned": earned,
            "earned_today": earned and earned_today_hints.get(bid, False),
        })
    return badges
