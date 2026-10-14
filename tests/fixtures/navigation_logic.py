"""Fixture: a known-good Developer Agent output, used for offline replay.

This is the exact artifact the agent produced in the previous project phase,
kept under tests/fixtures/ so the offline smoke test has a stable input that
is separate from the runtime artifact generated/navigation_logic.py.
"""

# Allowed actions the robot may perform.
ALLOWED_ACTIONS = ("FORWARD", "LEFT", "RIGHT", "STOP")

_GOAL_AHEAD = "AHEAD"
_GOAL_LEFT = "LEFT"
_GOAL_RIGHT = "RIGHT"


def _is_clear(direction, blocked):
    return not blocked


def _goal_direction(state):
    if state.get("goal_ahead"):
        return _GOAL_AHEAD
    if state.get("goal_on_left"):
        return _GOAL_LEFT
    if state.get("goal_on_right"):
        return _GOAL_RIGHT
    return None


def _decide_action(front_blocked, left_blocked, right_blocked, goal_direction):
    if goal_direction == _GOAL_AHEAD:
        return "FORWARD" if _is_clear("front", front_blocked) else "LEFT"
    if goal_direction == _GOAL_LEFT:
        return "LEFT" if _is_clear("left", left_blocked) else "RIGHT"
    if goal_direction == _GOAL_RIGHT:
        return "RIGHT" if _is_clear("right", right_blocked) else "FORWARD"
    return "STOP"


def decide_next_move(state):
    """Public entry point. This is the ONLY function other agents/programs call."""
    front_blocked = bool(state.get("front_blocked", False))
    left_blocked = bool(state.get("left_blocked", False))
    right_blocked = bool(state.get("right_blocked", False))

    goal_direction = _goal_direction(state)

    candidate = _decide_action(front_blocked, left_blocked, right_blocked, goal_direction)

    if candidate == "STOP":
        return "STOP"

    clear_for = {
        "FORWARD": not front_blocked,
        "LEFT": not left_blocked,
        "RIGHT": not right_blocked,
    }

    if clear_for.get(candidate, False):
        return candidate

    for action in ("FORWARD", "LEFT", "RIGHT"):
        if action != candidate and clear_for[action]:
            return action

    return "STOP"
