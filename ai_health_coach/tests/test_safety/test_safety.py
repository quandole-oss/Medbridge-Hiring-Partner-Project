import pytest
from langchain_core.messages import AIMessage

from app.graph.nodes.safety import (
    SafetyVerdict,
    crisis_handler_node,
    route_after_safety,
    safety_fallback_node,
)
from app.graph.prompts import CRISIS_RESPONSE, SAFETY_FALLBACK_RESPONSE


def test_safety_verdict_safe():
    verdict = SafetyVerdict(
        is_safe=True, violation_type="safe", explanation="Response is within scope"
    )
    assert verdict.is_safe is True
    assert verdict.violation_type == "safe"


def test_safety_verdict_clinical():
    verdict = SafetyVerdict(
        is_safe=False,
        violation_type="clinical_advice",
        explanation="Recommended medication",
    )
    assert verdict.is_safe is False


def test_safety_verdict_crisis():
    verdict = SafetyVerdict(
        is_safe=False, violation_type="crisis", explanation="Self-harm indicators"
    )
    assert verdict.violation_type == "crisis"


def test_route_after_safety_safe():
    state = {"_safety_verdict": "safe", "safety_retry_count": 0}
    assert route_after_safety(state) == "safe"


def test_route_after_safety_crisis():
    state = {"_safety_verdict": "crisis", "safety_retry_count": 0}
    assert route_after_safety(state) == "crisis"


def test_route_after_safety_retry():
    state = {"_safety_verdict": "clinical_advice", "safety_retry_count": 0}
    assert route_after_safety(state) == "retry"


def test_route_after_safety_fallback_after_retry():
    state = {"_safety_verdict": "clinical_advice", "safety_retry_count": 1}
    assert route_after_safety(state) == "fallback"


def test_route_after_safety_out_of_scope_retry():
    state = {"_safety_verdict": "out_of_scope", "safety_retry_count": 0}
    assert route_after_safety(state) == "retry"


def test_crisis_handler_returns_static_response():
    state = {
        "patient_id": "test-patient",
        "messages": [AIMessage(content="some response")],
    }
    result = crisis_handler_node(state)
    assert len(result["messages"]) == 1
    assert result["messages"][0].content == CRISIS_RESPONSE


def test_safety_fallback_returns_static_response():
    state = {"patient_id": "test-patient"}
    result = safety_fallback_node(state)
    assert result["messages"][0].content == SAFETY_FALLBACK_RESPONSE
