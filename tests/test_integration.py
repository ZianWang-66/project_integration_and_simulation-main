import json
from unittest.mock import patch
import pytest
from developer_agent import validate_developer_output, run_developer_revision
from reviewer_benchmark_agent import build_deterministic_review, run_benchmark_reviewer
from runner import run_simulation


def test_exhaustive_simulation():
    report = run_simulation("tests/fixtures/navigation_logic.py")
    assert report["total_scenarios"] == 64
    assert report["failed"] == 0


@pytest.mark.parametrize("code", ["def decide_next_move(): return 'STOP'",
                                  "def decide_next_move(a, b): return 'STOP'",
                                  "def decide_next_move(state, *args): return 'STOP'"])
def test_bad_signature(code):
    assert not validate_developer_output(code)


def test_missing_benchmark_is_not_pass():
    assert build_deterministic_review({})["needs_revision"]


def test_measured_results_override_model():
    report = {"total_worlds": 1, "success_rate": 0, "efficiency_rate": 0,
              "inefficient_success_worlds": 0,
              "results": [{"world": "failed", "reached_goal": False,
                           "collision_or_done": True, "efficiency_passed": False}]}
    fake = {"issue": "wrong", "likely_cause": "wrong", "recommendation": "wrong",
            "safety_passed": True, "goal_completion_passed": True,
            "efficiency_passed": True, "needs_revision": False}
    with patch("agent_utils.ask_agent", return_value=json.dumps(fake)):
        review = run_benchmark_reviewer(report)
    assert review["needs_revision"]
    assert not review["safety_passed"]
    assert not review["goal_completion_passed"]
    assert not review["efficiency_passed"]


def test_revision_receives_inputs_and_saves_separate_file(tmp_path):
    code = "def decide_next_move(state):\n    return 'STOP'\n"
    output = tmp_path / "revised.py"
    with patch("agent_utils.ask_agent", return_value=code) as model:
        result = run_developer_revision("old", {"issue": "failure"}, {"success_rate": 0},
                                        {"goal": "target"}, {"strategy": "safe"}, output)
    assert result == code.strip()
    assert output.read_text() == result
    sent = model.call_args.args[1]
    assert set(sent) == {"original_code", "review_notes", "benchmark_report", "requirements", "plan"}


def test_ollama_retries_503_without_thinking():
    from ollama import Client, ResponseError
    from ollama_client import ProjectClient
    with patch.object(Client, "chat", side_effect=[ResponseError("busy", 503), {"message": {"content": "OK"}}]) as chat:
        with patch("ollama_client.time.sleep"):
            result = ProjectClient().chat(model="qwen3:8b", messages=[])
    assert result["message"]["content"] == "OK"
    assert chat.call_count == 2
    assert chat.call_args.kwargs["think"] is False


def test_ollama_does_not_hide_persistent_503():
    from ollama import Client, ResponseError
    from ollama_client import ProjectClient
    with patch.object(Client, "chat", side_effect=ResponseError("busy", 503)) as chat:
        with patch("ollama_client.time.sleep"):
            with pytest.raises(ResponseError):
                ProjectClient().chat(model="qwen3:8b", messages=[])
    assert chat.call_count == 3


@pytest.mark.parametrize("wrapper", ["{}", "```json\n{}\n```", "<think>Analysis</think>\n{}", "Review:\n{}"])
def test_simulation_reviewer_accepts_json_wrappers(wrapper):
    from reviewer_agent import run_reviewer
    data = {"issue": "None", "likely_cause": "None", "recommendation": "Run benchmark", "needs_revision": False}
    with patch("agent_utils.ask_agent", return_value=wrapper.replace("{}", json.dumps(data))) as model:
        review = run_reviewer({"results": [{"passed": False}]})
    assert review["needs_revision"] is True
    assert model.call_args.kwargs["output_format"]["type"] == "object"


def test_simulation_reviewer_retries_invalid_response(tmp_path, monkeypatch):
    from reviewer_agent import run_reviewer
    monkeypatch.chdir(tmp_path)
    data = {"issue": "None", "likely_cause": "None", "recommendation": "Run benchmark", "needs_revision": False}
    with patch("agent_utils.ask_agent", side_effect=["", json.dumps(data)]) as model:
        review = run_reviewer({"results": []})
    assert model.call_count == 2
    assert not review["needs_revision"]
    assert (tmp_path / "artifacts/simulation_reviewer_raw_output.txt").exists()


def test_simulation_reviewer_rejects_repeated_invalid_response(tmp_path, monkeypatch):
    from reviewer_agent import run_reviewer
    monkeypatch.chdir(tmp_path)
    with patch("agent_utils.ask_agent", return_value='{"needs_revision": "false"}') as model:
        with pytest.raises(ValueError, match="failed after 3 attempts"):
            run_reviewer({"results": []})
    assert model.call_count == 3


def test_json_schema_is_sent_to_ollama():
    from agent_utils import ask_agent
    schema = {"type": "object"}
    with patch("agent_utils.ProjectClient.chat", return_value={"message": {"content": "{}"}}) as chat:
        assert ask_agent("Review", {}, output_format=schema) == "{}"
    assert chat.call_args.kwargs["format"] == schema
    assert chat.call_args.kwargs["think"] is False


@pytest.mark.parametrize("code", [
    "import pytest\nCASES = [\n    ({'goal_ahead': True}, 'FORWARD'),\n]\n\ndef test_case():\n    result = 'FORWARD'\n    assert result == CASES[0][1]",
    "import pytest\ndef test_case():\n    assert True\n\nTEST_DATA = [1, 2, 3]"
])
def test_python_extraction_preserves_valid_bare_source(code):
    from developer_agent import extract_python_code
    assert extract_python_code(code) == code


def test_test_agent_retries_and_keeps_raw_response(tmp_path, monkeypatch):
    from test_agent import run_test_agent
    monkeypatch.chdir(tmp_path)
    code = "import pytest\ndef test_example():\n    assert True"
    with patch("test_agent.ask_agent", side_effect=["Not Python", code]) as model:
        assert run_test_agent({}, {}, "source") == code
    assert model.call_count == 2
    assert (tmp_path / "artifacts/test_agent_raw_output.txt").read_text() == code


def test_test_agent_failure_saves_raw_response(tmp_path, monkeypatch):
    from test_agent import run_test_agent
    monkeypatch.chdir(tmp_path)
    with patch("test_agent.ask_agent", return_value="Not Python") as model:
        with pytest.raises(ValueError, match="failed after 3 attempts"):
            run_test_agent({}, {}, "source")
    assert model.call_count == 3
    assert (tmp_path / "artifacts/test_agent_raw_output.txt").read_text() == "Not Python"


def test_failed_pytest_is_included_in_revision_notes(tmp_path, monkeypatch):
    import subprocess
    import main as pipeline
    monkeypatch.chdir(tmp_path)
    (tmp_path / "generated").mkdir()
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts/irsim_benchmark_report.json").write_text("{}")
    review = {"issue": "None", "likely_cause": "None", "recommendation": "Run benchmark", "needs_revision": False}
    process = subprocess.CompletedProcess([], 1, stdout="test_goal failed", stderr="")
    with patch("main.run_test_agent", return_value="import pytest"):
        with patch("main.subprocess.run", return_value=process):
            with patch("main.run_simulation", return_value={"passed": 64, "failed": 0}):
                with patch("main.run_reviewer", return_value=review):
                    with patch("main.run_all_benchmarks", return_value={}):
                        with patch("main.run_benchmark_reviewer", return_value={}):
                            result = pipeline.evaluate({}, {}, "source", False, "initial")
    assert result[0]["needs_revision"] is True
    assert "test_goal failed" in result[0]["recommendation"]


def test_all_checks_stops_on_failure(tmp_path, monkeypatch):
    import subprocess
    import run_all_checks
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["run_all_checks.py", "--offline"])
    with patch("run_all_checks.os.chdir"):
        with patch("run_all_checks.subprocess.run", return_value=subprocess.CompletedProcess([], 1)) as command:
            assert run_all_checks.main() == 1
    report = json.loads((tmp_path / "artifacts/all_checks_report.json").read_text())
    assert not report["passed"]
    assert not report["completed"]
    assert command.call_count == 1


def test_stale_revision_file_does_not_verify_current_run(tmp_path, monkeypatch):
    from pathlib import Path
    import main as pipeline
    fixture_root = Path(__file__).resolve().parent / "fixtures"
    (tmp_path / "tests/fixtures").mkdir(parents=True)
    for name in ("requirements.json", "plan.json", "navigation_logic.py"):
        (tmp_path / "tests/fixtures" / name).write_bytes((fixture_root / name).read_bytes())
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated/navigation_logic_revised.py").write_text("stale code")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["main.py", "--offline"])
    with patch("main.os.chdir"):
        with patch("main.load_file", return_value="brief"):
            with patch("main.evaluate", return_value=({"needs_revision": False}, {}, {"needs_revision": False}, 0)):
                assert pipeline.main() == 0
    report = json.loads((tmp_path / "artifacts/pipeline_status.json").read_text())
    assert report["revision_attempts"] == 0
    assert report["llm_revision_verified"] is False
