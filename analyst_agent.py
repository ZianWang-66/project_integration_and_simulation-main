import ollama
import json
from ollama import Client


def load_file(filename):
    with open(filename, 'r') as file:
        brief_text = file.read()
    return brief_text

def run_analyst(brief_text):

    system_prompt = """
    You are a professional Requirements Engineer Analyst Agent.
    Your task: Extract explicit software requirements from the user's brief text, and output them strictly in valid JSON format.

    Rules you must follow:
    1. Output ONLY the JSON object, no extra explanation, no markdown code blocks, no comments, no prefix/suffix text.
    2. The navigation system can only use these actions: FORWARD, LEFT, RIGHT, STOP. No other actions allowed.
    3. Infer the navigation goal from the brief text, store it as a string in "goal".
    4. Judge whether the robot needs safe_stop and avoid_obstacles based on the brief description.

    Output JSON structure must be exactly:
    {
        "allowed_actions": ["FORWARD", "LEFT", "RIGHT", "STOP"],
        "goal": "the navigation objective string",
        "safe_stop": true/false,
        "avoid_obstacles": true/false
    }
    """
    client = Client(host="http://127.0.0.1:11434")
    response = client.chat(
        model="qwen3:8b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": brief_text}
        ]

    )


    json_text = response["message"]["content"]
    try:
        requirements = json.loads(json_text)
    except json.JSONDecodeError:
        raise ValueError("Qwen output is not valid JSON, please optimize the prompt.")

    if not validate_requirements(requirements):
        raise ValueError("Validation failed: requirements structure or type is incorrect.")

    return requirements



def validate_requirements(requirements):

     if not isinstance(requirements, dict):
         return False

     required_keys = {"goal", "allowed_actions", "safe_stop", "avoid_obstacles"}
     if set(requirements.keys()) != required_keys:
         return False

     if not isinstance(requirements["goal"], str):
        return False
     if not isinstance(requirements["allowed_actions"], list):
        return False
     if not isinstance(requirements["safe_stop"], bool):
        return False
     if not isinstance(requirements["avoid_obstacles"], bool):
        return False

     valid_actions = {"FORWARD", "LEFT", "RIGHT", "STOP"}
     if not set(requirements["allowed_actions"]).issubset(valid_actions):
         return False

     return True