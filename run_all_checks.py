import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--headless", action="store_true",
                        help="run the IR-SIM worlds without their windows")
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parent)
    Path("artifacts").mkdir(exist_ok=True)
    checks = []
    report_path = Path("artifacts/all_checks_report.json")
    pipeline_flags = ["--headless"] if args.headless else []
    commands = [
        ("Analyst fixture validation", ["tests/test_analyst.py", "--offline"]),
        ("Planner fixture validation", ["tests/test_planner.py", "--offline"]),
        ("Developer fixture validation", ["tests/test_developer.py", "--offline"]),
        ("Original navigation checks", ["tests/test_generated_navigation_logic.py"]),
        ("Full pytest suite", ["-m", "pytest", "-q"]),
        ("Offline pipeline and four IR-SIM worlds", ["main.py", "--offline"] + pipeline_flags)
    ]
    if not args.offline:
        commands.append(("Online Qwen pipeline with revision",
                         ["main.py", "--force-revision", "--max-revisions", "3"] + pipeline_flags))
    for name, command in commands:
        print("Running: " + name, flush=True)
        with Path("artifacts/all_checks_output.log").open("a", encoding="utf-8") as log:
            process = subprocess.run([sys.executable] + command, stdout=log, stderr=subprocess.STDOUT)
        checks.append({"name": name, "returncode": process.returncode, "passed": process.returncode == 0})
        passed = all(check["passed"] for check in checks)
        report = {"mode": "offline" if args.offline else "online", "completed": len(checks) == len(commands),
                  "passed": passed and len(checks) == len(commands), "checks": checks}
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if process.returncode:
            print("Failed: " + name + ". See artifacts/all_checks_output.log and trace.log", flush=True)
            return 1
        print("Passed: " + name, flush=True)
    print("All offline checks passed" if args.offline else "All checks passed, including the online revision pipeline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
