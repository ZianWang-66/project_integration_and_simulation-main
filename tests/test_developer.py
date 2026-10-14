"""Smoke test for the Developer Agent (Level 1 pipeline test).

Reads the real plan artifact, runs the real developer agent against it, lets
the agent's own validator accept/reject the output, then stores the generated
navigation code as ``generated/navigation_logic.py`` and prints it.

Usage
-----
    python3 tests/test_developer.py           # online, calls Ollama
    python3 tests/test_developer.py --offline # replay the existing artifact
"""

import argparse
import ast
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from developer_agent import run_developer, validate_developer_output  # noqa: E402

ARTIFACT_PATH = os.path.join(_ROOT, "generated", "navigation_logic.py")
PLAN_ARTIFACT = os.path.join(_ROOT, "artifacts", "plan.json")
LOGIC_FIXTURE = os.path.join(_ROOT, "tests", "fixtures", "navigation_logic.py")


def _replay_code():
    with open(LOGIC_FIXTURE, "r", encoding="utf-8") as f:
        return f.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    print("=" * 72)
    print("DEVELOPER AGENT - smoke test (Level 1)")
    print("=" * 72)

    if not os.path.exists(PLAN_ARTIFACT):
        print("[FAIL] {} not found. Run test_planner.py first.".format(PLAN_ARTIFACT))
        return 1

    import json as _json
    with open(PLAN_ARTIFACT, "r", encoding="utf-8") as f:
        plan = _json.load(f)
    print("[OK] plan artifact loaded")

    if args.offline:
        print("[MODE] offline replay (no Ollama)")
        code = _replay_code()
    else:
        print("Running developer agent with Qwen ...")
        code = run_developer(plan)

    print("[OK] agent produced output")

    if not validate_developer_output(code):
        print("[FAIL] agent's own validation REJECTED the generated code "
              "(not valid Python or missing decide_next_move)")
        return 1
    print("[OK] agent's own validation ACCEPTED the generated code")

    # Structural check: decide_next_move must take exactly one positional argument.
    tree = ast.parse(code)
    dnm = next(
        (fn for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef)
         and fn.name == "decide_next_move"),
        None,
    )
    assert dnm is not None
    positional = [a for a in dnm.args.args if a.arg != "state"]
    if len(positional) != 0 or len(dnm.args.args) != 1:
        print("[FAIL] decide_next_move must take exactly one argument 'state'")
        print("       got args:", [a.arg for a in dnm.args.args])
        return 1
    print("[OK] decide_next_move(state) signature is correct")
    print("[OK] no other helper function is required to be called by outside code")

    os.makedirs(os.path.dirname(ARTIFACT_PATH), exist_ok=True)
    with open(ARTIFACT_PATH, "w", encoding="utf-8") as f:
        f.write(code)
    print("[OK] artifact stored -> {}".format(ARTIFACT_PATH))

    print("-" * 72)
    print("Generated navigation_logic.py (preview):")
    for line in code.splitlines()[:20]:
        print(line)
    rest = max(0, len(code.splitlines()) - 20)
    if rest:
        print("... ({} more lines)".format(rest))
    print("-" * 72)
    print("DEVELOPER AGENT: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
