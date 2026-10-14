import json
import os
from pathlib import Path
from planner_agent import run_planner


## Create a function/logic that reads the requirements from requirements.json, 
# then calls the run_planner function with the requirements as input, and finally writes the validated plan to plan.json. 
def main():

    requirements_path = Path("artifacts") / "requirements.json"
    with open(requirements_path, "r") as f:
        requirements = json.load(f)

    print("Generating navigation plan with Qwen...")
    plan = run_planner(requirements)


    os.makedirs("artifacts", exist_ok=True)
    output_path = Path("artifacts") / "plan.json"
    with open(output_path, "w") as f:
        json.dump(plan, f, indent=2)

    print(f"Success! Valid plan saved to {output_path}")
    print("\nGenerated plan:")
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()