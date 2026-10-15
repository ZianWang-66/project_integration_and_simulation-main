import ast
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from agent_utils import save_json

WORLDS = ["irsim_worlds/world_" + name + ".yaml" for name in ("easy", "medium", "difficult", "custom")]
MAX_ATTEMPTS = 3
WORLD_TIMEOUT = 180


def run_world_process(world_file, headless=False):
    """Run one world in a fresh interpreter.

    By default the world runs with its window, which is the visible demo.  Pass
    ``headless=True`` for batch runs where no window should open.

    Returns ``(returncode, output, timed_out)``; ``returncode`` is ``None`` when
    the run had to be killed.
    """
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    command = [sys.executable, "test_irsim_with_agent.py", world_file]
    if headless:
        command.append("--headless")
    try:
        process = subprocess.run(command, capture_output=True, text=True, env=env,
                                 timeout=WORLD_TIMEOUT)
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or "") + (error.stderr or "")
        return None, output, True
    return process.returncode, process.stdout + process.stderr, False


def run_benchmark(world_file, headless=False, max_attempts=MAX_ATTEMPTS):
    if not Path(world_file).is_file():
        raise FileNotFoundError(world_file)
    name = Path(world_file).stem
    report_path = Path("artifacts/irsim_report.json")
    logs = []
    attempts = 0
    returncode, output = None, ""
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        report_path.unlink(missing_ok=True)
        logging.info("IR-SIM started world=%s attempt=%s", world_file, attempt)
        returncode, output, timed_out = run_world_process(world_file, headless=headless)
        logs.append("----- attempt %s (exit=%s) -----\n%s" % (attempt, returncode, output))
        if timed_out:
            # A hang comes from the code under test, so retrying only burns time.
            logging.error("IR-SIM timed out world=%s after %ss", world_file, WORLD_TIMEOUT)
            break
        if returncode == 0:
            if attempt > 1:
                logging.warning("IR-SIM %s succeeded on attempt %s", world_file, attempt)
            break
        logging.warning("IR-SIM attempt %s/%s failed for %s (exit=%s)",
                        attempt, max_attempts, world_file, returncode)
    Path("artifacts", name + ".log").write_text("\n".join(logs), encoding="utf-8")
    if returncode != 0:
        raise RuntimeError(f"IR-SIM failed in {world_file}; see artifacts/{name}.log")
    if report_path.exists():
        report = json.loads(report_path.read_text())
    else:
        report = ast.literal_eval(output.split("IR-SIM report:")[-1].strip())
    report["world"] = world_file
    report["attempts"] = attempts
    save_json(Path("artifacts", name + "_report.json"), report)
    logging.info("IR-SIM world=%s report=%s", world_file, report)
    return report


def run_all_benchmarks(headless=False):
    results = []
    for world in WORLDS:
        print("Running IR-SIM world: %s%s" % (world, "" if headless else " (window)"), flush=True)
        report = run_benchmark(world, headless=headless)
        print("  %s: goal %s in %s steps, collisions %s, min clearance %s" % (
            Path(world).stem, report["reached_goal"], report["steps_taken"],
            report.get("collisions"), report.get("min_clearance")), flush=True)
        results.append(report)
    total = len(results)
    reached = sum(r["reached_goal"] for r in results)
    efficient = sum(r["efficiency_passed"] for r in results)
    collisions = sum(r.get("collisions", 0) for r in results)
    report = {"total_worlds": total, "goals_reached": reached, "success_rate": reached / total,
              "efficient_worlds": efficient, "inefficient_success_worlds": reached - efficient,
              "failed_worlds": total - reached, "efficiency_rate": efficient / total,
              "collisions": collisions,
              "average_steps_taken": sum(r["steps_taken"] for r in results) / total, "results": results}
    save_json("artifacts/irsim_benchmark_report.json", report)
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the four IR-SIM worlds.")
    parser.add_argument("--headless", action="store_true",
                        help="no windows (batch mode)")
    args = parser.parse_args()
    print(json.dumps(run_all_benchmarks(headless=args.headless), indent=2))
