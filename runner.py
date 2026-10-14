import argparse
from agent_utils import load_navigation, save_json
from test_agent import scenarios, expected_action


def run_simulation(navigation_path="generated/navigation_logic.py"):
    decide = load_navigation(navigation_path)
    results = []
    for state in scenarios():
        expected = expected_action(state)
        try:
            actual = decide(state.copy())
            error = None
        except Exception as exc:
            actual, error = None, str(exc)
        results.append({"state": state, "expected": expected, "actual": actual,
                        "passed": actual == expected, "error": error})
    passed = sum(row["passed"] for row in results)
    return {"total_scenarios": len(results), "passed": passed,
            "failed": len(results) - passed, "success_rate": passed / len(results),
            "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--navigation", default="generated/navigation_logic.py")
    args = parser.parse_args()
    save_json("artifacts/simulation_report.json", run_simulation(args.navigation))
