"""Tests for weekly review node and graph routing."""
from unittest.mock import MagicMock, patch

import pytest

from app.graph.nodes.weekly_review import weekly_review_node
from app.graph.parent import route_by_phase
from app.graph.prompts import MI_TECHNIQUES_SECTION
from app.graph.state import Phase


class TestRouteByPhase:
    """Test that _weekly_review flag routes correctly."""

    def test_weekly_review_flag_routes_to_weekly_node(self):
        state = {
            "patient_id": "test",
            "current_phase": Phase.ACTIVE,
            "_weekly_review": True,
            "messages": [],
        }
        assert route_by_phase(state) == "weekly_review_node"

    def test_false_weekly_review_routes_normally(self):
        state = {
            "patient_id": "test",
            "current_phase": Phase.ACTIVE,
            "_weekly_review": False,
            "messages": [],
        }
        assert route_by_phase(state) == "active_coaching_node"

    def test_none_weekly_review_routes_normally(self):
        state = {
            "patient_id": "test",
            "current_phase": Phase.ONBOARDING,
            "_weekly_review": None,
            "messages": [],
        }
        assert route_by_phase(state) == "onboarding_node"

    def test_missing_weekly_review_routes_normally(self):
        state = {
            "patient_id": "test",
            "current_phase": Phase.RE_ENGAGING,
            "messages": [],
        }
        assert route_by_phase(state) == "re_engaging_node"


class TestWeeklyReviewNode:
    """Test the weekly review node."""

    @patch("app.graph.nodes.weekly_review.get_patient_insights")
    @patch("app.graph.nodes.weekly_review.get_adherence_summary")
    @patch("app.graph.nodes.weekly_review.get_conversation_llm")
    def test_produces_messages_and_clears_flag(
        self, mock_llm, mock_adherence, mock_insights
    ):
        mock_adherence.invoke.return_value = "completion_rate: 85.0, streak: 5"
        mock_insights.invoke.return_value = "Patient prefers morning workouts"

        mock_ai_response = MagicMock()
        mock_ai_response.content = "Great week! Here's your review..."
        mock_llm.return_value.invoke.return_value = mock_ai_response

        state = {
            "patient_id": "test-patient",
            "current_phase": Phase.ACTIVE,
            "current_goal": "Improve knee mobility",
            "_weekly_review": True,
            "messages": [],
        }

        result = weekly_review_node(state)

        assert "_weekly_review" in result
        assert result["_weekly_review"] is False
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "Great week! Here's your review..."

    @patch("app.graph.nodes.weekly_review.get_patient_insights")
    @patch("app.graph.nodes.weekly_review.get_adherence_summary")
    @patch("app.graph.nodes.weekly_review.get_conversation_llm")
    def test_includes_mi_section_for_low_adherence(
        self, mock_llm, mock_adherence, mock_insights
    ):
        mock_adherence.invoke.return_value = "completion_rate: 40.0, streak: 0"
        mock_insights.invoke.return_value = ""

        mock_ai_response = MagicMock()
        mock_ai_response.content = "Review with MI techniques"
        mock_llm.return_value.invoke.return_value = mock_ai_response

        state = {
            "patient_id": "test-patient",
            "current_phase": Phase.ACTIVE,
            "current_goal": "Walk 30 minutes",
            "_weekly_review": True,
            "messages": [],
        }

        result = weekly_review_node(state)

        # Verify the LLM was called with MI section in the prompt
        call_args = mock_llm.return_value.invoke.call_args[0][0]
        system_content = call_args[0].content
        assert "MOTIVATIONAL INTERVIEWING" in system_content

    @patch("app.graph.nodes.weekly_review.get_patient_insights")
    @patch("app.graph.nodes.weekly_review.get_adherence_summary")
    @patch("app.graph.nodes.weekly_review.get_conversation_llm")
    def test_no_mi_section_for_good_adherence(
        self, mock_llm, mock_adherence, mock_insights
    ):
        mock_adherence.invoke.return_value = "completion_rate: 90.0, streak: 7"
        mock_insights.invoke.return_value = ""

        mock_ai_response = MagicMock()
        mock_ai_response.content = "Standard review"
        mock_llm.return_value.invoke.return_value = mock_ai_response

        state = {
            "patient_id": "test-patient",
            "current_phase": Phase.ACTIVE,
            "current_goal": "Run 5K",
            "_weekly_review": True,
            "messages": [],
        }

        result = weekly_review_node(state)

        call_args = mock_llm.return_value.invoke.call_args[0][0]
        system_content = call_args[0].content
        assert "MOTIVATIONAL INTERVIEWING" not in system_content

    @patch("app.graph.nodes.weekly_review.get_patient_insights")
    @patch("app.graph.nodes.weekly_review.get_adherence_summary")
    @patch("app.graph.nodes.weekly_review.get_conversation_llm")
    def test_handles_llm_failure_gracefully(
        self, mock_llm, mock_adherence, mock_insights
    ):
        mock_adherence.invoke.return_value = "completion_rate: 80.0"
        mock_insights.invoke.return_value = ""
        mock_llm.return_value.invoke.side_effect = Exception("LLM error")

        state = {
            "patient_id": "test-patient",
            "current_phase": Phase.ACTIVE,
            "current_goal": "Get better",
            "_weekly_review": True,
            "messages": [],
        }

        result = weekly_review_node(state)

        assert result["_weekly_review"] is False
        assert len(result["messages"]) == 1
        # Should return fallback message
        assert "trouble" in result["messages"][0].content.lower()
