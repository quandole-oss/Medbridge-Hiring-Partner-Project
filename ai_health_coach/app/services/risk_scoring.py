"""Pure heuristic risk scoring for patients — no DB, no LLM."""
from typing import Optional


def compute_risk_score(
    adherence: dict,
    outcomes: dict,
    difficulty: dict,
    phase: str,
    days_since_last_message: Optional[int],
    open_alert_counts: dict,
) -> dict:
    """Compute a deterministic risk score (0-100) from patient signals.

    Returns {"score": int, "level": str, "factors": dict}
    """
    factors = {}

    # 1. Adherence rate (max 25)
    rate = adherence.get("completion_rate", 0)
    if rate < 30:
        factors["adherence"] = 25
    elif rate < 50:
        factors["adherence"] = 18
    elif rate < 70:
        factors["adherence"] = 10
    elif rate < 85:
        factors["adherence"] = 4
    else:
        factors["adherence"] = 0

    # 2. Pain trend (max 20)
    pain_trend = outcomes.get("pain_trend", "stable")
    if pain_trend == "declining":  # pain increasing = bad
        factors["pain_trend"] = 20
    elif pain_trend == "stable":
        factors["pain_trend"] = 5
    else:
        factors["pain_trend"] = 0

    # 3. Days since last message (max 15)
    days = days_since_last_message if days_since_last_message is not None else 0
    if days >= 7:
        factors["inactivity"] = 15
    elif days >= 4:
        factors["inactivity"] = 10
    elif days >= 2:
        factors["inactivity"] = 5
    else:
        factors["inactivity"] = 0

    # 4. Difficulty pattern (max 15)
    total_feedback = (
        difficulty.get("too_hard", 0)
        + difficulty.get("too_easy", 0)
        + difficulty.get("just_right", 0)
    )
    if total_feedback > 0:
        hard_ratio = difficulty.get("too_hard", 0) / total_feedback
        if hard_ratio > 0.5:
            factors["difficulty"] = 15
        elif hard_ratio > 0.25:
            factors["difficulty"] = 8
        else:
            factors["difficulty"] = 0
    else:
        factors["difficulty"] = 0

    # 5. Phase (max 10)
    phase_scores = {
        "dormant": 10,
        "re_engaging": 6,
        "onboarding": 3,
        "active": 0,
        "pending": 0,
    }
    factors["phase"] = phase_scores.get(phase, 0)

    # 6. Streak (max 10)
    streak = adherence.get("streak", 0)
    if streak == 0:
        factors["streak"] = 10
    elif streak <= 2:
        factors["streak"] = 6
    elif streak <= 4:
        factors["streak"] = 3
    else:
        factors["streak"] = 0

    # 7. Open alerts (max 5)
    if open_alert_counts.get("critical", 0) > 0:
        factors["alerts"] = 5
    elif open_alert_counts.get("high", 0) > 0:
        factors["alerts"] = 3
    elif open_alert_counts.get("low", 0) > 0:
        factors["alerts"] = 1
    else:
        factors["alerts"] = 0

    score = min(sum(factors.values()), 100)

    if score <= 20:
        level = "low"
    elif score <= 45:
        level = "medium"
    elif score <= 70:
        level = "high"
    else:
        level = "critical"

    return {"score": score, "level": level, "factors": factors}
