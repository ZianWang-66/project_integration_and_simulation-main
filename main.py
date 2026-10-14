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
from runner import run_simulation
from reviewer_agent import run_reviewer
from benchmark_irsim import run_all_benchmarks
from reviewer_benchmark_agent import run_benchmark_reviewer
from agent_utils import save_json


def evaluate(requirements, plan, code, offline, label):
    logging.info("%s Test Agent started", label)
    tests = run_test_agent(requirements, plan, code, offline)
    Path("generated/test_navigation.py").write_text(tests, encoding="utf-8")
    process = subprocess.run([sys.executable, "-m", "pytest", "generated/test_navigation.py", "-q"],
                             capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(Path.cwd())))
    Path("artifacts", label + "_pytest.txt").write_text(process.stdout + process.stderr)
    logging.info("%s pytest returncode=%s", label, process.returncode)
    report = run_simulation()
    save_json("artifacts/simulation_report.json", report)
    logging.info("%s Simulation created simulation_report.json: %s/64 passed", label, report["passed"])
    review = run_reviewer(report, offline)
    if process.returncode:
        review["needs_revision"] = True
        review["issue"] += "; Generated pytest tests failed"
        review["recommendation"] += "\nFix the following pytest failures:\n" + (process.stdout + process.stderr)[-6000:]
    save_json("artifacts/simulation_review.json", review)
    logging.info("%s Reviewer created simulation_review.json", label)
    benchmark = run_all_benchmarks()
    logging.info("%s IR-SIM benchmark created irsim_benchmark_report.json", label)
    benchmark_review = run_benchmark_reviewer(benchmark, offline)
    save_json("artifacts/benchmark_review.json", benchmark_review)
    logging.info("%s Benchmark Reviewer created benchmark_review.json", label)
    snapshot = Path("artifacts", label)
    snapshot.mkdir(exist_ok=True)
    for filename in ("simulation_report.json", "simulation_review.json", "irsim_benchmark_report.json", "benchmark_review.json"):
        (snapshot / filename).write_bytes((Path("artifacts") / filename).read_bytes())
    return review, benchmark, benchmark_review, process.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Replay supplied fixtures; no LLM calls or LLM revision")
    parser.add_argument("--max-revisions", type=int, default=1)
    parser.add_argument("--force-revision", action="store_true", help="Demonstrate one Qwen revision even when initial benchmarks pass")
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
        Path("generated/navigation_logic.py").write_text(code, encoding="utf-8")
        logging.info("Saved requirements, plan, navigation code")
        if args.offline:
            logging.info("Analyst and Planner fixture replay finished; Developer fixture replay finished")
        review, benchmark, benchmark_review, test_status = evaluate(requirements, plan, code, args.offline, "initial")
        revision_count = 0
        for number in range(args.max_revisions):
            if not (review["needs_revision"] or benchmark_review["needs_revision"] or test_status or (args.force_revision and number == 0)):
                break
            if args.offline:
                logging.warning("Revision required; offline mode cannot claim an LLM revision")
                break
            code = run_developer_revision(code, {"simulation": review, "benchmark": benchmark_review},
                                          benchmark, requirements, plan)
            logging.info("Developer revision saved navigation_logic_revised.py")
            Path("generated/navigation_logic.py").write_text(code, encoding="utf-8")
            review, benchmark, benchmark_review, test_status = evaluate(requirements, plan, code, False, f"revision_{number + 1}")
            revision_count += 1
        passed = not (review["needs_revision"] or benchmark_review["needs_revision"] or test_status)
        save_json("artifacts/pipeline_status.json", {"mode": "offline" if args.offline else "online", "passed": passed,
                  "revision_attempts": revision_count,
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
