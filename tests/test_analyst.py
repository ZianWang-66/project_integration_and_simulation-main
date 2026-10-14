"""Smoke test for the Analyst Agent (Level 1 pipeline test).

Runs the real analyst agent against the original brief.txt, lets the agent's
own validator accept/reject the output, then stores the artifact as
``artifacts/requirements.json`` and prints it.

Usage
-----
Online (real Ollama at http://127.0.0.1:11434):
    python3 tests/test_analyst.py

Offline replay (no Ollama available, e.g. in CI / this sandbox):
    python3 tests/test_analyst.py --offline
"""

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from analyst_agent import load_file, run_analyst, validate_requirements  # noqa: E402

ARTIFACT_PATH = os.path.join(_ROOT, "artifacts", "requirements.json")
BRIEF_PATH = os.path.join(_ROOT, "brief.txt")
REQUIREMENTS_FIXTURE = os.path.join(_ROOT, "tests", "fixtures", "requirements.json")


def _replay_requirements():
    """Return the artifact produced by a previous real analyst run."""
    with open(REQUIREMENTS_FIXTURE, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true",
                        help="replay the real artifact instead of calling Ollama")
    args = parser.parse_args()

    print("=" * 72)
    print("ANALYST AGENT - smoke test (Level 1)")
    print("=" * 72)

    brief_text = load_file(BRIEF_PATH)
    print("[OK] brief.txt loaded ({} chars)".format(len(brief_text.strip())))

    if args.offline:
        print("[MODE] offline replay (no Ollama)")
        requirements = _replay_requirements()
    else:
        print("Running analyst agent with Qwen ...")
        requirements = run_analyst(brief_text)

    print("[OK] agent produced output")

    if not validate_requirements(requirements):
        print("[FAIL] agent's own validation REJECTED the requirements")
        print(json.dumps(requirements, indent=2))
        return 1
    print("[OK] agent's own validation ACCEPTED the requirements")

    os.makedirs(os.path.dirname(ARTIFACT_PATH), exist_ok=True)
    with open(ARTIFACT_PATH, "w", encoding="utf-8") as f:
        json.dump(requirements, f, indent=2)
    print("[OK] artifact stored -> {}".format(ARTIFACT_PATH))

    print("-" * 72)
    print("Generated requirements.json:")
    print(json.dumps(requirements, indent=2))
    print("-" * 72)
    print("ANALYST AGENT: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
