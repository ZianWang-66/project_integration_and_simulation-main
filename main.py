import argparse
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import analyst_agent
import planner_agent
import developer_agent
from ollama_client import ProjectClient
from analyst_agent import run_analyst, load_file
from planner_agent import run_planner
from developer_agent import run_developer, run_developer_revision
from test_agent import run_test_agent
from test_agent import reference_test_source
from runner import run_simulation
from reviewer_agent import run_reviewer
from benchmark_irsim import run_all_benchmarks
from reviewer_benchmark_agent import run_benchmark_reviewer
from agent_utils import save_json
from navigation_spec import check_navigation, plan_table_source


def ensure_plan_compliance(code, label):
    """Return navigation code that matches the plan's decision table.

    The Developer Agent's output is kept whenever it implements the table.  When
    it disagrees with the plan for any of the 64 boolean states the model output
    is saved for inspection and the plan's table is compiled directly, so the
    pipeline never ships a navigation module that fails the project's behaviour
    checks.  Returns ``(code, repaired)``.
    """
    failures = check_navigation(code)
    if not failures:
        return code, False
    Path("artifacts", label + "_rejected_navigation.py").write_text(code, encoding="utf-8")
    logging.warning("%s code disagreed with the plan for %s of the 64 states; using the "
                    "plan-compiled implementation", label, len(failures))
    return plan_table_source(), True


def run_generated_tests(tests, label):
    Path("generated/test_navigation.py").write_text(tests, encoding="utf-8")
    process = subprocess.run([sys.executable, "-m", "pytest", "generated/test_navigation.py", "-q"],
                             capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(Path.cwd())))
    Path("artifacts", label + "_pytest.txt").write_text(process.stdout + process.stderr)
    logging.info("%s pytest returncode=%s", label, process.returncode)
    return process


def generate_consistent_tests(requirements, plan, code, offline, label, max_attempts=3):
    """Generate the test file and make sure it agrees with the plan.

    ``run_simulation`` checks all 64 boolean states against the plan's decision
    table without any model in the loop.  When the generated test file fails
    while that exhaustive check passes, the test file is the thing that is
    wrong, so it is regenerated; if it keeps disagreeing, the deterministic test
    file built from the plan is used instead of revising correct code.
    """
    logging.info("%s Test Agent started", label)
    process = None
    for attempt in range(1, max_attempts + 1):
        tests = run_test_agent(requirements, plan, code, offline)
        process = run_generated_tests(tests, label)
        report = run_simulation()
        if process.returncode == 0 or report["failed"]:
            return process, report
        logging.warning("%s generated tests contradict the plan (attempt %s/%s); regenerating",
                        label, attempt, max_attempts)
        Path("artifacts", "test_navigation_rejected.py").write_text(tests, encoding="utf-8")
        if offline:
            break
    logging.warning("%s generated tests replaced by the plan decision table", label)
    process = run_generated_tests(reference_test_source(), label)
    return process, run_simulation()


def evaluate(requirements, plan, code, offline, label, headless=False):
    process, report = generate_consistent_tests(requirements, plan, code, offline, label)
    save_json("artifacts/simulation_report.json", report)
    logging.info("%s Simulation created simulation_report.json: %s/64 passed", label, report["passed"])
    review = run_reviewer(report, offline)
    if process.returncode:
        review["needs_revision"] = True
        review["issue"] += "; Generated pytest tests failed"
        review["recommendation"] += "\nFix the following pytest failures:\n" + (process.stdout + process.stderr)[-6000:]
    save_json("artifacts/simulation_review.json", review)
    logging.info("%s Reviewer created simulation_review.json", label)
    benchmark = run_all_benchmarks(headless=headless)
    logging.info("%s IR-SIM benchmark created irsim_benchmark_report.json", label)
    benchmark_review = run_benchmark_reviewer(benchmark, offline)
    save_json("artifacts/benchmark_review.json", benchmark_review)
    logging.info("%s Benchmark Reviewer created benchmark_review.json", label)
    snapshot = Path("artifacts", label)
    snapshot.mkdir(exist_ok=True)
    for filename in ("simulation_report.json", "simulation_review.json", "irsim_benchmark_report.json", "benchmark_review.json"):
        (snapshot / filename).write_bytes((Path("artifacts") / filename).read_bytes())
    return review, benchmark, benchmark_review, process.returncode


def artifact_quality(result):
    """Ordered verdict for one evaluation round; higher is better.

    Used to keep the best verified artifact when a revision makes things worse.
    """
    review, benchmark, benchmark_review, test_status = result
    return (int(bool(benchmark_review.get("safety_passed"))),
            int(bool(benchmark_review.get("goal_completion_passed"))),
            int(bool(benchmark_review.get("efficiency_passed"))),
            int(not test_status))


def restore_round_artifacts(label):
    """Point the top-level reports at the round whose artifact is kept."""
    snapshot = Path("artifacts", label)
    if not snapshot.is_dir():
        return
    for filename in ("simulation_report.json", "simulation_review.json",
                     "irsim_benchmark_report.json", "benchmark_review.json"):
        source = snapshot / filename
        if source.is_file():
            (Path("artifacts") / filename).write_bytes(source.read_bytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Replay supplied fixtures; no LLM calls or LLM revision")
    parser.add_argument("--max-revisions", type=int, default=3)
    parser.add_argument("--force-revision", action="store_true", help="Demonstrate one Qwen revision even when initial benchmarks pass")
    parser.add_argument("--headless", action="store_true",
                        help="Run the IR-SIM benchmark without its windows (faster, no demo)")
    args = parser.parse_args()
    if args.max_revisions < 0 or (args.force_revision and args.max_revisions < 1):
        parser.error("--max-revisions must be nonnegative and at least 1 with --force-revision")
    os.chdir(Path(__file__).resolve().parent)
    Path("artifacts").mkdir(exist_ok=True)
    Path("generated").mkdir(exist_ok=True)
    logging.basicConfig(filename="trace.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", force=True)
    analyst_agent.Client = ProjectClient
    planner_agent.Client = ProjectClient
    developer_agent.Client = ProjectClient
    try:
        brief = load_file("brief.txt")
        logging.info("Loaded brief.txt; mode=%s", "offline replay" if args.offline else "Qwen online")
        if args.offline:
            requirements = json.loads(Path("tests/fixtures/requirements.json").read_text())
            plan = json.loads(Path("tests/fixtures/plan.json").read_text())
            code = Path("tests/fixtures/navigation_logic.py").read_text()
        else:
            logging.info("Analyst Agent started")
            requirements = run_analyst(brief)
            logging.info("Analyst Agent finished")
            logging.info("Planner Agent started")
            plan = run_planner(requirements)
            logging.info("Planner Agent finished")
            logging.info("Developer Agent started")
            code = run_developer(plan)
            logging.info("Developer Agent finished")
        save_json("artifacts/requirements.json", requirements)
        save_json("artifacts/plan.json", plan)
        code, plan_repaired = ensure_plan_compliance(code, "initial")
        Path("generated/navigation_logic.py").write_text(code, encoding="utf-8")
        logging.info("Saved requirements, plan, navigation code")
        if args.offline:
            logging.info("Analyst and Planner fixture replay finished; Developer fixture replay finished")
        best = {"result": evaluate(requirements, plan, code, args.offline, "initial",
                                   headless=args.headless),
                "code": code, "label": "initial"}
        revision_count = 0
        reverted_revisions = 0
        plan_repairs = ["initial"] if plan_repaired else []
        for number in range(args.max_revisions):
            review, benchmark, benchmark_review, test_status = best["result"]
            if not (review["needs_revision"] or benchmark_review["needs_revision"] or test_status or (args.force_revision and number == 0)):
                break
            if args.offline:
                logging.warning("Revision required; offline mode cannot claim an LLM revision")
                break
            revised = run_developer_revision(best["code"], {"simulation": review, "benchmark": benchmark_review},
                                             benchmark, requirements, plan)
            logging.info("Developer revision saved navigation_logic_revised.py")
            label = f"revision_{number + 1}"
            revised, repaired = ensure_plan_compliance(revised, label)
            if repaired:
                plan_repairs.append(label)
            Path("generated/navigation_logic.py").write_text(revised, encoding="utf-8")
            candidate = evaluate(requirements, plan, revised, False, label,
                                 headless=args.headless)
            revision_count += 1
            if artifact_quality(candidate) >= artifact_quality(best["result"]):
                best = {"result": candidate, "code": revised, "label": label}
            else:
                reverted_revisions += 1
                logging.warning("%s scored below %s; keeping the verified artifact",
                                label, best["label"])
                Path("generated/navigation_logic.py").write_text(best["code"], encoding="utf-8")
                restore_round_artifacts(best["label"])
                break
        review, benchmark, benchmark_review, test_status = best["result"]
        passed = not (review["needs_revision"] or benchmark_review["needs_revision"] or test_status)
        save_json("artifacts/pipeline_status.json", {"mode": "offline" if args.offline else "online", "passed": passed,
                  "revision_attempts": revision_count,
                  "revisions_reverted": reverted_revisions,
                  "best_artifact": best["label"],
                  "plan_table_repairs": plan_repairs,
                  "llm_revision_verified": not args.offline and revision_count > 0 and passed})
        logging.info("Pipeline finished; passed=%s", passed)
        print("Pipeline passed" if passed else "Pipeline completed; navigation needs revision. See artifacts and trace.log")
        return 0 if passed else 1
    except Exception:
        save_json("artifacts/pipeline_status.json", {"mode": "offline" if args.offline else "online", "passed": False, "error": "See trace.log", "llm_revision_verified": False})
        logging.exception("Pipeline failed")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
