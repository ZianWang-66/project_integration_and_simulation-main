import json
import logging
import re
from pathlib import Path
from ollama_client import ProjectClient


def ask_agent(prompt, data, output_format=None):
    extra = {"format": output_format} if output_format is not None else {}
    response = ProjectClient(host="http://127.0.0.1:11434").chat(
        model="qwen3:8b", think=False, **extra,
        messages=[{"role": "system", "content": prompt},
                  {"role": "user", "content": json.dumps(data)}])
    return response["message"]["content"].strip()


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_navigation(path):
    namespace = {}
    exec(compile(Path(path).read_text(encoding="utf-8"), str(path), "exec"), namespace)
    return namespace["decide_next_move"]


def parse_json_reply(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if not text:
        raise ValueError("Empty model response")
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise ValueError("Model response contains no JSON object")
        result, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def ask_json_agent(prompt, data, schema, validator, label, max_attempts=3):
    for attempt in range(max_attempts):
        raw = ask_agent(prompt, data, output_format=schema)
        try:
            result = parse_json_reply(raw)
            if not validator(result):
                raise ValueError("Response does not match the required schema")
            return result
        except (ValueError, TypeError) as error:
            path = Path("artifacts", label + "_raw_output.txt")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(raw, encoding="utf-8")
            logging.warning("%s invalid JSON attempt %s/%s: %s", label, attempt + 1, max_attempts, error)
    raise ValueError(f"{label} failed after {max_attempts} attempts; see artifacts/{label}_raw_output.txt")
