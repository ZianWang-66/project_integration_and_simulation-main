"""Behavioral tests for the generated navigation logic.

Level 2 testing (per the project instructions): call ``decide_next_move(state)``
with known sensor states and assert that the returned action is both a *valid*
action AND the *expected* action for that state.

The state dict uses these boolean keys:
    goal_ahead, goal_on_left, goal_on_right,
    front_blocked, left_blocked, right_blocked
"""

import os
import sys

# Make the generated artifact importable when running this file directly.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from generated.navigation_logic import decide_next_move


VALID_ACTIONS = {"FORWARD", "LEFT", "RIGHT", "STOP"}


def _case(description, state, expected):
    """Run one test case and return (description, passed, detail)."""
    action = decide_next_move(state)
    valid = action in VALID_ACTIONS
    correct = action == expected
    passed = valid and correct
    detail = "action={!r} expected={!r}".format(action, expected)
    return description, passed, detail


def main():
    cases = [
        # ---- Goal ahead ----
        ("goal ahead, path clear",
         {"goal_ahead": True, "goal_on_left": False, "goal_on_right": False,
          "front_blocked": False, "left_blocked": False, "right_blocked": False},
         "FORWARD"),

        ("goal ahead, front blocked, left clear",
         {"goal_ahead": True, "goal_on_left": False, "goal_on_right": False,
          "front_blocked": True, "left_blocked": False, "right_blocked": False},
         "LEFT"),

        ("goal ahead, front + left blocked, right clear",
         {"goal_ahead": True, "goal_on_left": False, "goal_on_right": False,
          "front_blocked": True, "left_blocked": True, "right_blocked": False},
         "RIGHT"),

        ("goal ahead, all sides blocked -> must STOP",
         {"goal_ahead": True, "goal_on_left": False, "goal_on_right": False,
          "front_blocked": True, "left_blocked": True, "right_blocked": True},
         "STOP"),

        # ---- Goal on the left ----
        ("goal left, path clear",
         {"goal_ahead": False, "goal_on_left": True, "goal_on_right": False,
          "front_blocked": False, "left_blocked": False, "right_blocked": False},
         "LEFT"),

        ("goal left, left blocked, right clear",
         {"goal_ahead": False, "goal_on_left": True, "goal_on_right": False,
          "front_blocked": True, "left_blocked": True, "right_blocked": False},
         "RIGHT"),

        ("goal left, left + right blocked, front clear",
         {"goal_ahead": False, "goal_on_left": True, "goal_on_right": False,
          "front_blocked": False, "left_blocked": True, "right_blocked": True},
         "FORWARD"),

        ("goal left, all blocked -> STOP",
         {"goal_ahead": False, "goal_on_left": True, "goal_on_right": False,
          "front_blocked": True, "left_blocked": True, "right_blocked": True},
         "STOP"),

        # ---- Goal on the right ----
        ("goal right, path clear",
         {"goal_ahead": False, "goal_on_left": False, "goal_on_right": True,
          "front_blocked": False, "left_blocked": False, "right_blocked": False},
         "RIGHT"),

        ("goal right, right blocked, front clear",
         {"goal_ahead": False, "goal_on_left": False, "goal_on_right": True,
          "front_blocked": False, "left_blocked": True, "right_blocked": True},
         "FORWARD"),

        ("goal right, right + front blocked, left clear",
         {"goal_ahead": False, "goal_on_left": False, "goal_on_right": True,
          "front_blocked": True, "left_blocked": False, "right_blocked": True},
         "LEFT"),

        ("goal right, all blocked -> STOP",
         {"goal_ahead": False, "goal_on_left": False, "goal_on_right": True,
          "front_blocked": True, "left_blocked": True, "right_blocked": True},
         "STOP"),

        # ---- No goal known -> stay safe ----
        ("no goal known, all clear -> safe STOP (no direction to pursue)",
         {"goal_ahead": False, "goal_on_left": False, "goal_on_right": False,
          "front_blocked": False, "left_blocked": False, "right_blocked": False},
         "STOP"),

        ("no goal known, all blocked -> STOP",
         {"goal_ahead": False, "goal_on_left": False, "goal_on_right": False,
          "front_blocked": True, "left_blocked": True, "right_blocked": True},
         "STOP"),
    ]

    passed_total = 0
    failed_total = 0
    for description, expected_action, state in [
        (d, e, s) for d, s, e in [(c[0], c[1], c[2]) for c in cases]]:
        pass

    # clearer: just iterate the cases directly
    for description, state, expected in cases:
        _, ok, detail = _case(description, state, expected)
        if ok:
            passed_total += 1
            print("[PASS] {:<60} ({})".format(description, detail))
        else:
            failed_total += 1
            print("[FAIL] {:<60} ({})".format(description, detail))

    print("-" * 72)
    print("Results: {} passed, {} failed, {} total".format(
        passed_total, failed_total, len(cases)))

    return 0 if failed_total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
