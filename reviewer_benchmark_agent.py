import json
from agent_utils import ask_json_agent

BENCHMARK_REVIEW_SYSTEM_PROMPT = """
Review IR-SIM metrics and deterministic review. Output only JSON with issue,
likely_cause, recommendation as strings and safety_passed, goal_completion_passed,
efficiency_passed, needs_revision as booleans. Name the failing worlds and measured
steps. Recommend a specific fix. Keep measured boolean values unchanged.
"""


BENCHMARK_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {key: {"type": "string"} for key in ("issue", "likely_cause", "recommendation")},
    "required": ["issue", "likely_cause", "recommendation", "safety_passed",
                 "goal_completion_passed", "efficiency_passed", "needs_revision"],
    "additionalProperties": False
}
for key in ("safety_passed", "goal_completion_passed", "efficiency_passed", "needs_revision"):
    BENCHMARK_REVIEW_SCHEMA["properties"][key] = {"type": "boolean"}


def validate_benchmark_review(data):
    strings = ("issue", "likely_cause", "recommendation")
    booleans = ("safety_passed", "goal_completion_passed", "efficiency_passed", "needs_revision")
    if (not isinstance(data, dict) or set(data) != set(strings + booleans)
            or not all(isinstance(data[k], str) for k in strings)
            or not all(type(data[k]) is bool for k in booleans)):
        raise ValueError("Invalid benchmark review")
    return True


def build_deterministic_review(report):
    results = report.get("results", [])
    complete = bool(results) and len(results) == report.get("total_worlds", 0)
    safety = complete and not any(r.get("collision_or_done", True) and not r.get("reached_goal", False) for r in results)
    goal = complete and report.get("success_rate", 0) == 1.0
    efficiency = complete and report.get("inefficient_success_worlds", 1) == 0 and report.get("efficiency_rate", 0) == 1.0
    issues = []
    if not safety: issues.append("Unsafe benchmark behavior detected")
    if not goal: issues.append("Goal completion failure")
    if not efficiency: issues.append("Successful but inefficient navigation")
    failed = [{"world": r.get("world"), "steps": r.get("steps_taken"),
               "reached_goal": r.get("reached_goal")} for r in results if not r.get("efficiency_passed", False)]
    return {"issue": "; ".join(issues) or "All benchmark requirements passed",
            "likely_cause": json.dumps(failed) if issues else "None",
            "recommendation": "Review obstacle fallback and turn oscillation in the listed worlds, then rerun all four worlds" if issues else "No revision needed",
            "safety_passed": safety, "goal_completion_passed": goal,
            "efficiency_passed": efficiency, "needs_revision": not (safety and goal and efficiency)}


def run_benchmark_reviewer(report, offline=False):
    measured = build_deterministic_review(report)
    review = measured if offline else ask_json_agent(
        BENCHMARK_REVIEW_SYSTEM_PROMPT, {"report": report, "deterministic_review": measured},
        BENCHMARK_REVIEW_SCHEMA, validate_benchmark_review, "benchmark_reviewer")
    validate_benchmark_review(review)
    for key in ("safety_passed", "goal_completion_passed", "efficiency_passed", "needs_revision"):
        review[key] = measured[key]
    return review
