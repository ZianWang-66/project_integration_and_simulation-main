from generated.navigation_logic import decide_next_move

def test_goal_ahead_front_clear():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": False,
        "right_blocked": False
    }
    assert decide_next_move(state) == "FORWARD"

def test_goal_ahead_front_blocked():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": False,
        "right_blocked": False
    }
    assert decide_next_move(state) == "LEFT"

def test_goal_on_left_left_clear():
    state = {
        "goal_ahead": False,
        "goal_on_left": True,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": False,
        "right_blocked": False
    }
    assert decide_next_move(state) == "LEFT"

def test_goal_on_left_left_blocked():
    state = {
        "goal_ahead": False,
        "goal_on_left": True,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": True,
        "right_blocked": False
    }
    assert decide_next_move(state) == "RIGHT"

def test_goal_on_right_right_clear():
    state = {
        "goal_ahead": False,
        "goal_on_left": False,
        "goal_on_right": True,
        "front_blocked": False,
        "left_blocked": False,
        "right_blocked": False
    }
    assert decide_next_move(state) == "RIGHT"

def test_goal_on_right_right_blocked():
    state = {
        "goal_ahead": False,
        "goal_on_left": False,
        "goal_on_right": True,
        "front_blocked": False,
        "left_blocked": False,
        "right_blocked": True
    }
    assert decide_next_move(state) == "FORWARD"

def test_no_goal_directions_all_blocked():
    state = {
        "goal_ahead": False,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": True,
        "right_blocked": True
    }
    assert decide_next_move(state) == "STOP"

def test_goal_ahead_front_blocked_left_blocked():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": True,
        "right_blocked": False
    }
    assert decide_next_move(state) == "STOP"

def test_goal_on_left_left_blocked_right_clear():
    state = {
        "goal_ahead": False,
        "goal_on_left": True,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": True,
        "right_blocked": False
    }
    assert decide_next_move(state) == "RIGHT"

def test_goal_on_right_right_blocked_front_clear():
    state = {
        "goal_ahead": False,
        "goal_on_left": False,
        "goal_on_right": True,
        "front_blocked": False,
        "left_blocked": False,
        "right_blocked": True
    }
    assert decide_next_move(state) == "FORWARD"

def test_goal_ahead_front_blocked_left_clear():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": False,
        "right_blocked": True
    }
    assert decide_next_move(state) == "LEFT"

def test_goal_on_left_left_blocked_front_clear():
    state = {
        "goal_ahead": False,
        "goal_on_left": True,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": True,
        "right_blocked": False
    }
    assert decide_next_move(state) == "RIGHT"

def test_goal_on_right_right_blocked_left_clear():
    state = {
        "goal_ahead": False,
        "goal_on_left": False,
        "goal_on_right": True,
        "front_blocked": False,
        "left_blocked": False,
        "right_blocked": True
    }
    assert decide_next_move(state) == "LEFT"

def test_goal_ahead_front_blocked_right_clear():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": True,
        "right_blocked": False
    }
    assert decide_next_move(state) == "STOP"

def test_goal_on_left_left_blocked_right_blocked():
    state = {
        "goal_ahead": False,
        "goal_on_left": True,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": True,
        "right_blocked": True
    }
    assert decide_next_move(state) == "STOP"

def test_goal_on_right_right_blocked_front_blocked():
    state = {
        "goal_ahead": False,
        "goal_on_left": False,
        "goal_on_right": True,
        "front_blocked": True,
        "left_blocked": False,
        "right_blocked": True
    }
    assert decide_next_move(state) == "STOP"

def test_goal_ahead_front_blocked_left_blocked_right_clear():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": True,
        "right_blocked": False
    }
    assert decide_next_move(state) == "STOP"

def test_goal_on_left_left_blocked_right_blocked_front_clear():
    state = {
        "goal_ahead": False,
        "goal_on_left": True,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": True,
        "right_blocked": True
    }
    assert decide_next_move(state) == "STOP"

def test_goal_on_right_right_blocked_front_blocked_left_clear():
    state = {
        "goal_ahead": False,
        "goal_on_left": False,
        "goal_on_right": True,
        "front_blocked": True,
        "left_blocked": False,
        "right_blocked": True
    }
    assert decide_next_move(state) == "LEFT"

def test_goal_ahead_front_blocked_left_clear_right_blocked():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": False,
        "right_blocked": True
    }
    assert decide_next_move(state) == "LEFT"

def test_goal_on_left_left_blocked_front_clear_right_blocked():
    state = {
        "goal_ahead": False,
        "goal_on_left": True,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": True,
        "right_blocked": True
    }
    assert decide_next_move(state) == "STOP"

def test_goal_on_right_right_blocked_front_clear_left_blocked():
    state = {
        "goal_ahead": False,
        "goal_on_left": False,
        "goal_on_right": True,
        "front_blocked": False,
        "left_blocked": True,
        "right_blocked": True
    }
    assert decide_next_move(state) == "STOP"

def test_goal_ahead_front_blocked_left_blocked_right_blocked():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": True,
        "right_blocked": True
    }
    assert decide_next_move(state) == "STOP"

def test_goal_on_left_left_blocked_front_blocked_right_clear():
    state = {
        "goal_ahead": False,
        "goal_on_left": True,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": True,
        "right_blocked": False
    }
    assert decide_next_move(state) == "STOP"

def test_goal_on_right_right_blocked_front_blocked_left_clear():
    state = {
        "goal_ahead": False,
        "goal_on_left": False,
        "goal_on_right": True,
        "front_blocked": True,
        "left_blocked": False,
        "right_blocked": True
    }
    assert decide_next_move(state) == "LEFT"

def test_goal_ahead_front_blocked_left_clear_right_blocked():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": False,
        "right_blocked": True
    }
    assert decide_next_move(state) == "LEFT"

def test_goal_on_left_left_blocked_front_clear_right_blocked():
    state = {
        "goal_ahead": False,
        "goal_on_left": True,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": True,
        "right_blocked": True
    }
    assert decide_next_move(state) == "STOP"

def test_goal_on_right_right_blocked_front_clear_left_blocked():
    state = {
        "goal_ahead": False,
        "goal_on_left": False,
        "goal_on_right": True,
        "front_blocked": False,
        "left_blocked": True,
        "right_blocked": True
    }
    assert decide_next_move(state) == "STOP"

def test_goal_ahead_front_blocked_left_blocked_right_clear():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": True,
        "right_blocked": False
    }
    assert decide_next_move(state) == "STOP"

def test_goal_on_left_left_blocked_front_blocked_right_clear():
    state = {
        "goal_ahead": False,
        "goal_on_left": True,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": True,
        "right_blocked": False
    }
    assert decide_next_move(state) == "STOP"

def test_goal_on_right_right_blocked_front_blocked_left_clear():
    state = {
        "goal_ahead": False,
        "goal_on_left": False,
        "goal_on_right": True,
        "front_blocked": True,
        "left_blocked": False,
        "right_blocked": True
    }
    assert decide_next_move(state) == "LEFT"

def test_goal_ahead_front_blocked_left_clear_right_blocked():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": True,
        "left_blocked": False,
        "right_blocked": True
    }
    assert decide_next_move(state) == "LEFT"

def test_goal_on_left_left_blocked_front_clear_right_blocked():
    state = {
        "goal_ahead": False,
        "goal_on_left": True,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": True,
        "right_blocked": True
    }
    assert decide_next_move(state) == "STOP"

def test_goal_on_right_right_blocked_front_clear_left_blocked():
    state = {
        "goal_ahead": False,
        "goal_on_left": False,
        "goal_on_right": True,
        "front_blocked": False,
        "left_blocked": True,
        "right_blocked": True
    }
    assert decide_next_move(state) == "STOP"