## The logic is fairly similar to the Analyst and Planner agents
import ast
import json
import logging
import os
from ollama import Client
from navigation_spec import DECISION_ORDER, check_navigation


def _mismatch_feedback(failures, limit=4):
    """Feedback for an output that does not match the plan's decision table.

    Each wrong state is explained step by step, because the resolution order
    (goal direction first, then the fallback order) is easy to misread.
    """
    wrong = json.dumps(
        [{"state": f["state"], "your_action": f["actual"], "plan_action": f["expected"]}
         for f in failures[:limit]], indent=2)
    why = "\n".join("- " + f.get("why", "") for f in failures[:limit])
    return (
        "\n\nYour previous code disagreed with the plan's decision table for "
        f"{len(failures)} of the 64 boolean states. The first wrong states were:\n"
        + wrong
        + "\nWhy the plan returns those actions:\n" + why
        + "\nThe plan resolves a state by " + DECISION_ORDER + "."
        + "\nRewrite the branch structure so every state follows that order, and "
        "return only corrected Python source code."
    )


## System prompt for the Developer Agent
DEVELOPER_SYSTEM_PROMPT = """
You are a professional Python Developer Agent.
Your task: Based on the validated navigation plan, write complete, working Python code that implements the robot navigation logic.

Rules you must follow:
1. Output ONLY the Python code, no extra explanation, no markdown code blocks, no comments outside the code.
2. The robot can only perform these actions: FORWARD, LEFT, RIGHT, STOP. No other actions allowed.
3. The code must define exactly ONE public entry-point function named `decide_next_move`, which is the ONLY function other agents/programs will ever call.
4. `decide_next_move` MUST accept a SINGLE argument `state`, a dict with these keys (all bool):
       goal_ahead, goal_on_left, goal_on_right,
       front_blocked, left_blocked, right_blocked
   and return the chosen action as a str.
5. You may define any private helper functions you like (e.g. `decide_action`), but they must NOT be called by outside code. Only `decide_next_move` is public.
6. The code must follow the navigation strategy and decisions from the plan exactly,
   which means:
     * resolve the goal direction first: use goal_ahead when it is set, otherwise
       goal_on_left, otherwise goal_on_right (a state may have more than one goal
       flag set, and this order decides which one wins);
     * pursue that direction: FORWARD when the goal is ahead, LEFT when it is on
       the left, RIGHT when it is on the right;
     * when that action is blocked, use the first unblocked action in this order:
       the goal-direction action, then FORWARD, then LEFT, then RIGHT;
     * return STOP only when all three directions are blocked, or when no goal
       direction is known at all.
7. The code must implement safe stop when no safe direction is available.
8. The code must be syntactically valid Python and ready to run.

The function signature must be EXACTLY:
    def decide_next_move(state: dict) -> str:
        # state keys: goal_ahead, goal_on_left, goal_on_right,
        #             front_blocked, left_blocked, right_blocked
        # returns one of: "FORWARD", "LEFT", "RIGHT", "STOP"

Return only the Python source code.
"""


## Function to validate the developer output
def validate_developer_output(code):
    """Validate that the output is syntactically valid Python code and
    exposes the mandatory public entry point `decide_next_move(state)`."""
    if not isinstance(code, str) or len(code.strip()) == 0:
        return False

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    # Check that it contains at least one function definition
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    if len(functions) == 0:
        return False

    # Mandatory public entry point for this project.
    if not any(fn.name == "decide_next_move" for fn in functions):
        return False

    entries = [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name == "decide_next_move"]
    if len(entries) != 1:
        return False
    args = entries[0].args
    return (len(args.posonlyargs) + len(args.args) == 1
            and not args.vararg and not args.kwarg and not args.kwonlyargs
            and not args.defaults)



def extract_python_code(raw_text):
    if not isinstance(raw_text, str):
        return ""
    text = raw_text.strip()
    if not text:
        return ""

    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    try:
        ast.parse(text)
        return text
    except SyntaxError:
        pass

    lines = text.split("\n")

    fence_idx = [i for i, line in enumerate(lines) if line.strip().startswith("```")]
    if fence_idx:
        if len(fence_idx) >= 2:
            code = "\n".join(lines[fence_idx[0] + 1 : fence_idx[-1]])
        else:
            code = "\n".join(lines[fence_idx[0] + 1 :])
        code = code.strip()

        if code.endswith("```"):
            code = code[:-3].strip()
        return code

    start = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if (s.startswith(("def ", "class ", "import ", "from ", "@"))
                or s.startswith("async def ")):
            start = i
            break
    code = "\n".join(lines[start:]).strip()

    if code:
        code_lines = code.split("\n")
        cut = len(code_lines)

        code_starters = (
            "def ", "class ", "import ", "from ", "if ", "elif ", "else:",
            "for ", "while ", "try:", "except", "finally:", "with ",
            "return", "print(", "@", "#", "async def ",
        )
        for i in range(len(code_lines) - 1, -1, -1):
            s = code_lines[i].strip()
            if s == "" or s.startswith((" ", "\t")):
                continue
            if s.startswith(code_starters):
                continue

            cut = i
            break
        code = "\n".join(code_lines[:cut]).strip()

    return code


## Function to run the Developer Agent
def run_developer(plan, max_attempts=3):
    client = Client(host="http://127.0.0.1:11434")


    user_content = json.dumps(plan, indent=2)

    last_raw_output = ""
    best_code, best_failures = None, None
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            user_content += "\n\n" + retry_note

        response = client.chat(
            model="qwen3:8b",
            messages=[
                {"role": "system", "content": DEVELOPER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Here is the validated navigation plan:\n{user_content}\n\nWrite the Python navigation logic code."}
            ]
        )

        raw_output = response["message"]["content"]
        last_raw_output = raw_output
        code_text = extract_python_code(raw_output)

        if validate_developer_output(code_text):
            failures = check_navigation(code_text)
            if not failures:
                return code_text
            retry_note = _mismatch_feedback(failures)
            if best_failures is None or len(failures) < len(best_failures):
                best_code, best_failures = code_text, failures
        else:
            retry_note = (
                "Your previous output FAILED validation: it was not syntactically "
                "valid Python, or it contained no function definition.\n"
                "Now output ONLY pure Python source code. No explanations, no markdown "
                "fences (```), no text before or after the code."
            )

    if best_code is not None:
        logging.warning("Developer output still disagrees with the plan for %s of 64 states",
                        len(best_failures))
        return best_code

    os.makedirs("artifacts", exist_ok=True)
    raw_path = os.path.join("artifacts", "developer_raw_output.txt")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(last_raw_output)
    raise ValueError(
        f"Validation failed after {max_attempts} attempts: generated code is not valid "
        "Python or has no function. The last raw model output was saved to "
        f"{raw_path} for inspection."
    )


def run_developer_revision(original_code, review_notes, benchmark_report, requirements, plan,
                           output_path="generated/navigation_logic_revised.py", max_attempts=3):
    from pathlib import Path
    from agent_utils import ask_agent
    data = {"original_code": original_code, "review_notes": review_notes,
            "benchmark_report": benchmark_report, "requirements": requirements, "plan": plan}
    prompt = DEVELOPER_SYSTEM_PROMPT + "\nRevise the original code using measured failures. Check every fallback for obstacles. Avoid repeated turn oscillation."
    best_code, best_failures = None, None
    for attempt in range(max_attempts):
        code = extract_python_code(ask_agent(prompt, data))
        if validate_developer_output(code):
            failures = check_navigation(code)
            if not failures:
                path = Path(output_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(code, encoding="utf-8")
                return code
            prompt += _mismatch_feedback(failures)
            if best_failures is None or len(failures) < len(best_failures):
                best_code, best_failures = code, failures
        else:
            data["validation_error"] = "Return valid Python with decide_next_move(state)."
    if best_code is not None:
        logging.warning("Revision still disagrees with the plan for %s of 64 states",
                        len(best_failures))
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(best_code, encoding="utf-8")
        return best_code
    raise ValueError("Developer revision failed validation")
