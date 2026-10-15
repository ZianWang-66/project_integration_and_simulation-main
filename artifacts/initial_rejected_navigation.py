def decide_next_move(state: dict) -> str:
    goal_direction = None
    if state["goal_ahead"]:
        goal_direction = "FORWARD"
    elif state["goal_on_left"]:
        goal_direction = "LEFT"
    elif state["goal_on_right"]:
        goal_direction = "RIGHT"
    
    if goal_direction is None:
        return "STOP"
    
    if goal_direction == "FORWARD" and not state["front_blocked"]:
        return "FORWARD"
    elif goal_direction == "LEFT" and not state["left_blocked"]:
        return "LEFT"
    elif goal_direction == "RIGHT" and not state["right_blocked"]:
        return "RIGHT"
    
    priority_order = ["FORWARD", "LEFT", "RIGHT"]
    for action in priority_order:
        if action == "FORWARD" and not state["front_blocked"]:
            return "FORWARD"
        elif action == "LEFT" and not state["left_blocked"]:
            return "LEFT"
        elif action == "RIGHT" and not state["right_blocked"]:
            return "RIGHT"
    
    return "STOP"