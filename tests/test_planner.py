"""Smoke test for the Planner Agent (Level 1 pipeline test).

Reads the real requirements artifact, runs the real planner agent against it,
lets the agent's own validator accept/reject the output, then stores the
result as ``artifacts/plan.json`` and prints it.

Usage
-----
    python3 tests/test_planner.py           # online, calls Ollama
    python3 tests/test_planner.py --offline # replay the real artifact
"""

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from planner_agent import run_planner, validate_plan  # noqa: E402

ARTIFACT_PATH = os.path.join(_ROOT, "artifacts", "plan.json")
REQUIREMENTS_ARTIFACT = os.path.join(_ROOT, "artifacts", "requirements.json")
PLAN_FIXTURE = os.path.join(_ROOT, "tests", "fixtures", "plan.json")


def _replay_plan():
    with open(PLAN_FIXTURE, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    print("=" * 72)
    print("PLANNER AGENT - smoke test (Level 1)")
    print("=" * 72)

    if not os.path.exists(REQUIREMENTS_ARTIFACT):
        print("[FAIL] {} not found. Run test_analyst.py first.".format(
            REQUIREMENTS_ARTIFACT))
        return 1

    with open(REQUIREMENTS_ARTIFACT, "r", encoding="utf-8") as f:
        requirements = json.load(f)
    print("[OK] requirements artifact loaded")

    if args.offline:
        print("[MODE] offline replay (no Ollama)")
        plan = _replay_plan()
    else:
        print("Running planner agent with Qwen ...")
        plan = run_planner(requirements)

    print("[OK] agent produced output")

    if not validate_plan(plan):
        print("[FAIL] agent's own validation REJECTED the plan")
        print(json.dumps(plan, indent=2))
        return 1
    print("[OK] agent's own validation ACCEPTED the plan")

    # The plan must be consumable by the developer agent.
    valid_actions = {"FORWARD", "LEFT", "RIGHT", "STOP"}
    usable = (
        isinstance(plan, dict)
        and "decisions" in plan
        and isinstance(plan["decisions"], list)
        and len(plan["decisions"]) > 0
        and all(
            isinstance(d, dict)
            and d.get("action") in valid_actions
            and "condition" in d
            for d in plan["decisions"]
        )
    )
    if not usable:
        print("[FAIL] plan is not usable by the developer agent")
        return 1
    print("[OK] plan is usable by the developer agent")

    os.makedirs(os.path.dirname(ARTIFACT_PATH), exist_ok=True)
    with open(ARTIFACT_PATH, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
    print("[OK] artifact stored -> {}".format(ARTIFACT_PATH))

    print("-" * 72)
    print("Generated plan.json:")
    print(json.dumps(plan, indent=2))
    print("-" * 72)
    print("PLANNER AGENT: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
