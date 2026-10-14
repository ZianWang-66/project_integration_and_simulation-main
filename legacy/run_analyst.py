from analyst_agent import load_file, run_analyst
import os
import json



def main():
    brief_text = load_file('brief.txt')

    print("Analyzing brief with Qwen...")
    requirements = run_analyst(brief_text)

    os.makedirs("artifacts", exist_ok=True)

    output_path = os.path.join("artifacts", "requirements.json")
    with open(output_path, "w") as file:
        json.dump(requirements, file, indent=2)

    print(f"Success! Valid requirements saved to {output_path}")
    print("\nGenerated requirements: ")
    print(json.dumps(requirements, indent=2 ))

if __name__ == "__main__":
    main()