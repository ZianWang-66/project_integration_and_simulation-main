## the logic is similar to the run_planner and run_analyst files
import json
from pathlib import Path
from developer_agent import run_developer


def main():

    plan_path = Path("artifacts") / "plan.json"
    with open(plan_path, "r") as f:
        plan = json.load(f)

    print("Generating navigation code with Qwen...")
    code = run_developer(plan)


    output_path = Path("navigation_logic.py")
    with open(output_path, "w") as f:
        f.write(code)

    print(f"Success! Navigation code saved to {output_path}")
    print("\nGenerated code preview (first 20 lines):")
    lines = code.split("\n")
    for line in lines[:20]:
        print(line)
    if len(lines) > 20:
        print(f"... ({len(lines) - 20} more lines)")


if __name__ == "__main__":
    main()
