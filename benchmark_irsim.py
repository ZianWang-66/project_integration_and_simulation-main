import ast
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from agent_utils import save_json

WORLDS = ["irsim_worlds/world_" + name + ".yaml" for name in ("easy", "medium", "difficult", "custom")]


def run_benchmark(world_file):
    if not Path(world_file).is_file():
        raise FileNotFoundError(world_file)
    logging.info("IR-SIM started world=%s", world_file)
    report_path = Path("artifacts/irsim_report.json")
    report_path.unlink(missing_ok=True)
    env = dict(os.environ, MPLBACKEND="Agg")
    process = subprocess.run([sys.executable, "test_irsim_with_agent.py", world_file],
                             capture_output=True, text=True, env=env, timeout=180)
    name = Path(world_file).stem
    Path("artifacts", name + ".log").write_text(process.stdout + process.stderr, encoding="utf-8")
    if process.returncode:
        raise RuntimeError(f"IR-SIM failed in {world_file}; see artifacts/{name}.log")
    if report_path.exists():
        report = json.loads(report_path.read_text())
    else:
        report = ast.literal_eval(process.stdout.split("IR-SIM report:")[-1].strip())
    report["world"] = world_file
    save_json(Path("artifacts", name + "_report.json"), report)
    logging.info("IR-SIM world=%s report=%s", world_file, report)
    return report


def run_all_benchmarks():
    results = [run_benchmark(world) for world in WORLDS]
    total = len(results)
    reached = sum(r["reached_goal"] for r in results)
    efficient = sum(r["efficiency_passed"] for r in results)
    report = {"total_worlds": total, "goals_reached": reached, "success_rate": reached / total,
              "efficient_worlds": efficient, "inefficient_success_worlds": reached - efficient,
              "failed_worlds": total - reached, "efficiency_rate": efficient / total,
              "average_steps_taken": sum(r["steps_taken"] for r in results) / total, "results": results}
    save_json("artifacts/irsim_benchmark_report.json", report)
    return report


if __name__ == "__main__":
    print(json.dumps(run_all_benchmarks(), indent=2))
