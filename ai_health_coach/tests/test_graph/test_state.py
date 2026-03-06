from app.graph.state import GraphState, Phase


def test_phase_enum_values():
    assert Phase.PENDING == "pending"
    assert Phase.ONBOARDING == "onboarding"
    assert Phase.ACTIVE == "active"
    assert Phase.RE_ENGAGING == "re_engaging"
    assert Phase.DORMANT == "dormant"


def test_phase_string_comparison():
    assert Phase.ACTIVE == "active"
    assert "active" == Phase.ACTIVE
