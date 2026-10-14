def decide_action(front_blocked: bool, left_blocked: bool, right_blocked: bool, goal_direction: str) -> str:
    if goal_direction == "AHEAD" and not front_blocked:
        return "FORWARD"
    elif goal_direction == "AHEAD" and front_blocked:
        return "LEFT"
    elif goal_direction == "LEFT" and not left_blocked:
        return "LEFT"
    elif goal_direction == "LEFT" and left_blocked:
        return "RIGHT"
    elif goal_direction == "RIGHT" and not right_blocked:
        return "RIGHT"
    elif goal_direction == "RIGHT" and right_blocked:
        return "FORWARD"
    else:
        return "STOP"