import ast
import itertools
import logging
from pathlib import Path
from agent_utils import ask_agent
from developer_agent import extract_python_code

KEYS = ("goal_ahead", "goal_on_left", "goal_on_right",
        "front_blocked", "left_blocked", "right_blocked")
TEST_SYSTEM_PROMPT = """
Generate only Python pytest code importing decide_next_move from generated.navigation_logic.
Use requirements, plan and navigation source. Test all 64 combinations of six boolean
state keys: goal_ahead, goal_on_left, goal_on_right, front_blocked, left_blocked,
right_blocked. Assert allowed actions, obstacle avoidance, safe stop and goal priority.
Never compute expected values by calling the implementation. Include import and assert.
Use pytest functions named test_* and plain assert statements, not unittest classes.
Output only complete Python source code, without prose or markdown.
"""


def expected_action(state):
    if state["goal_ahead"]:
        preferred = "FORWARD" if not state["front_blocked"] else "LEFT"
    elif state["goal_on_left"]:
        preferred = "LEFT" if not state["left_blocked"] else "RIGHT"
    elif state["goal_on_right"]:
        preferred = "RIGHT" if not state["right_blocked"] else "FORWARD"
    else:
        return "STOP"
    blocked = dict(zip(("FORWARD", "LEFT", "RIGHT"),
                       (state["front_blocked"], state["left_blocked"], state["right_blocked"])))
    for action in (preferred, "FORWARD", "LEFT", "RIGHT"):
        if not blocked[action]:
            return action
    return "STOP"


def scenarios():
    return [dict(zip(KEYS, values)) for values in itertools.product((False, True), repeat=6)]


def validate_test_output(code):
    if not isinstance(code, str) or not code.strip() or "```" in code:
        return False
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    return (any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(tree))
            and any(isinstance(n, ast.Assert) for n in ast.walk(tree))
            and any(isinstance(n, ast.FunctionDef) and n.name.startswith("test_") for n in ast.walk(tree)))


def run_test_agent(requirements, plan, navigation_code, offline=False, max_attempts=3):
    if offline:
        rows = [(s, expected_action(s)) for s in scenarios()]
        code = ('import pytest\nfrom generated.navigation_logic import decide_next_move\n'
                + '@pytest.mark.parametrize("state, expected", ' + repr(rows) + ')\n'
                + 'def test_all_states(state, expected):\n    assert decide_next_move(state) == expected\n')
        if not validate_test_output(code):
            raise ValueError("Invalid offline test code")
        return code
    data = {"requirements": requirements, "plan": plan, "navigation_code": navigation_code}
    path = Path("artifacts/test_agent_raw_output.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(max_attempts):
        raw = ask_agent(TEST_SYSTEM_PROMPT, data)
        path.write_text(raw, encoding="utf-8")
        code = extract_python_code(raw)
        if validate_test_output(code):
            return code
        logging.warning("Test Agent invalid code attempt %s/%s", attempt + 1, max_attempts)
        data["validation_error"] = "Return complete Python pytest code containing imports, a test_* function, and assert statements."
    raise ValueError(f"Test Agent failed after {max_attempts} attempts; see {path}")
