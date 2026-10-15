"""The navigation contract shared by the agents and the verifiers.

The plan resolves one boolean sensor state in a fixed order:

1. pursue the goal direction when that direction is not blocked (FORWARD when
   the goal is ahead, LEFT when it is on the left, RIGHT when it is on the
   right);
2. otherwise take the first unblocked action in the order goal-direction
   action, FORWARD, LEFT, RIGHT;
3. return STOP only when all three directions are blocked.

``expected_action`` is the machine-readable form of that table.  The simulation
runner, the generated tests and the Developer Agent's self-check all use it, so
"follows the plan" has exactly one meaning across the pipeline.
"""

import itertools

KEYS = ("goal_ahead", "goal_on_left", "goal_on_right",
        "front_blocked", "left_blocked", "right_blocked")

DECISION_ORDER = (
    "resolving the goal direction first (use goal_ahead when it is set, otherwise "
    "goal_on_left, otherwise goal_on_right) and only then choosing an action: the "
    "goal-direction action first, then FORWARD, then LEFT, then RIGHT; STOP only "
    "when all three directions are blocked"
)


def scenarios():
    return [dict(zip(KEYS, values)) for values in itertools.product((False, True), repeat=6)]


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


def load_from_source(code):
    """Import ``decide_next_move`` from Python source text."""
    namespace = {}
    exec(compile(code, "<navigation_logic>", "exec"), namespace)
    return namespace["decide_next_move"]


def check_navigation(code):
    """Return the states in which *code* disagrees with the plan's table."""
    try:
        decide = load_from_source(code)
    except Exception as error:
        return [{"state": None, "expected": "an importable decide_next_move",
                 "actual": f"{type(error).__name__}: {error}"}]
    failures = []
    for state in scenarios():
        try:
            actual = decide(dict(state))
        except Exception as error:
            actual = f"{type(error).__name__}: {error}"
        if actual != expected_action(state):
            failures.append({"state": state, "expected": expected_action(state),
                             "actual": actual, "why": explain_action(state)})
    return failures


def explain_action(state):
    """Narrate how the plan resolves one state, for repair feedback."""
    steps = []
    if state["goal_ahead"]:
        extra = " and it wins even though another goal flag is set" \
            if state["goal_on_left"] or state["goal_on_right"] else ""
        steps.append("goal_ahead is set" + extra)
        preferred = "FORWARD" if not state["front_blocked"] else "LEFT"
        if state["front_blocked"]:
            steps.append("the goal is ahead but the front path is blocked, so the goal action is LEFT")
    elif state["goal_on_left"]:
        steps.append("goal_ahead is not set and goal_on_left is")
        preferred = "LEFT" if not state["left_blocked"] else "RIGHT"
        if state["left_blocked"]:
            steps.append("the left path is blocked, so the goal action is RIGHT")
    elif state["goal_on_right"]:
        steps.append("only goal_on_right is set")
        preferred = "RIGHT" if not state["right_blocked"] else "FORWARD"
        if state["right_blocked"]:
            steps.append("the right path is blocked, so the goal action is FORWARD")
    else:
        return "no goal flag is set, so the plan returns STOP"
    blocked = {"FORWARD": state["front_blocked"], "LEFT": state["left_blocked"],
               "RIGHT": state["right_blocked"]}
    order = [preferred] + [action for action in ("FORWARD", "LEFT", "RIGHT")
                           if action != preferred]
    for action in order:
        if not blocked[action]:
            steps.append("the first unblocked action in the order %s is %s"
                         % (", ".join(order), action))
            return "; ".join(steps)
    steps.append("every direction is blocked, so the plan returns STOP")
    return "; ".join(steps)


_PLAN_TABLE_SOURCE = '''"""Navigation logic compiled directly from the plan's decision table.

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
'''


def plan_table_source():
    """The plan's decision table as a ready-to-run navigation module."""
    return _PLAN_TABLE_SOURCE
