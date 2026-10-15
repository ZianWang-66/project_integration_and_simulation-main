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

    clear = {"FORWARD": not front_blocked, "LEFT": not left_blocked, "RIGHT": not right_blocked}
    for action in (preferred, "FORWARD", "LEFT", "RIGHT"):
        if clear[action]:
            return action
    return "STOP"