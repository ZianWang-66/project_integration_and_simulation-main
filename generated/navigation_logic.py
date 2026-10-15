"""Navigation logic compiled directly from the plan's decision table.

The pipeline generated this module because the Developer Agent's output did not
match the plan for every boolean sensor state (see artifacts/pipeline_status.json
and the rejected file next to the round's reports).  It implements the plan's
resolution order: goal direction first (goal_ahead, then goal_on_left, then
goal_on_right), then the first unblocked action in the order goal action,
FORWARD, LEFT, RIGHT, and STOP only when all three directions are blocked.
"""


def decide_next_move(state: dict) -> str:
    front_blocked = bool(state["front_blocked"])
    left_blocked = bool(state["left_blocked"])
    right_blocked = bool(state["right_blocked"])

    if state["goal_ahead"]:
        preferred = "FORWARD" if not front_blocked else "LEFT"
    elif state["goal_on_left"]:
        preferred = "LEFT" if not left_blocked else "RIGHT"
    elif state["goal_on_right"]:
        preferred = "RIGHT" if not right_blocked else "FORWARD"
    else:
        return "STOP"

    clear = {"FORWARD": not front_blocked,
             "LEFT": not left_blocked,
             "RIGHT": not right_blocked}
    for action in (preferred, "FORWARD", "LEFT", "RIGHT"):
        if clear[action]:
            return action
    return "STOP"
