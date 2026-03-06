import pytest

from app.graph.parent import route_by_phase
from app.graph.state import Phase


def test_route_onboarding():
    state = {"current_phase": Phase.ONBOARDING}
    assert route_by_phase(state) == "onboarding_node"


def test_route_active():
    state = {"current_phase": Phase.ACTIVE}
    assert route_by_phase(state) == "active_coaching_node"


def test_route_re_engaging():
    state = {"current_phase": Phase.RE_ENGAGING}
    assert route_by_phase(state) == "re_engaging_node"


def test_route_dormant():
    state = {"current_phase": Phase.DORMANT}
    assert route_by_phase(state) == "dormant_handler"


def test_route_pending_raises():
    state = {"current_phase": Phase.PENDING}
    with pytest.raises(ValueError, match="Undefined phase route"):
        route_by_phase(state)


def test_route_invalid_raises():
    state = {"current_phase": "nonexistent"}
    with pytest.raises(ValueError, match="Undefined phase route"):
        route_by_phase(state)
