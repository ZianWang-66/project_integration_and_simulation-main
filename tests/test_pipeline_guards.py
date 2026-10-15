"""Tests for the pipeline guards against unreliable model output.

The Developer Agent must follow the plan's decision table, the Test Agent's file
must agree with it, and a revision may not leave the repository with a worse
artifact than the round it replaced.
"""

import json
import subprocess
from pathlib import Path

import main as pipeline
from navigation_spec import check_navigation, plan_table_source
from reviewer_agent import run_reviewer
from test_agent import reference_test_source

FIXTURE_CODE = (Path(__file__).resolve().parent / "fixtures" / "navigation_logic.py").read_text(
    encoding="utf-8")
WRONG_CODE = "def decide_next_move(state):\n    return 'STOP'\n"


class _ScriptedClient:
    """Ollama client stub returning the given outputs in order."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        content = self.outputs[min(len(self.calls) - 1, len(self.outputs) - 1)]
        return {"message": {"content": content}}


def test_developer_retries_until_the_plan_table_matches(monkeypatch):
    import developer_agent

    client = _ScriptedClient([WRONG_CODE, FIXTURE_CODE])
    monkeypatch.setattr(developer_agent, "Client", lambda **kwargs: client)

    code = developer_agent.run_developer({"strategy": "go"})

    assert len(client.calls) == 2
    assert check_navigation(code) == []
    feedback = client.calls[1]["messages"][1]["content"]
    assert "plan_action" in feedback and "FORWARD" in feedback


def test_developer_returns_the_closest_output_when_nothing_matches(monkeypatch):
    import developer_agent

    monkeypatch.setattr(developer_agent, "Client", lambda **kwargs: _ScriptedClient([WRONG_CODE]))

    code = developer_agent.run_developer({"strategy": "go"}, max_attempts=2)

    assert code.strip() == WRONG_CODE.strip()
    assert check_navigation(code), "the plan check should report the mismatch"


def test_revision_returns_the_closest_output_when_nothing_matches(tmp_path, monkeypatch):
    import developer_agent

    monkeypatch.setattr("agent_utils.ask_agent", lambda prompt, data, **kwargs: WRONG_CODE)
    output = tmp_path / "revised.py"

    code = developer_agent.run_developer_revision("original", {}, {}, {}, {},
                                                  output_path=str(output), max_attempts=2)

    assert code.strip() == WRONG_CODE.strip()
    assert output.read_text(encoding="utf-8") == code


def test_generated_tests_are_replaced_when_they_contradict_the_plan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "generated").mkdir()
    llm_tests = "import pytest\n\ndef test_generated():\n    assert False\n"
    written = []

    def fake_run_generated_tests(tests, label):
        written.append(tests)
        failing = tests == llm_tests
        return subprocess.CompletedProcess([], 1 if failing else 0, stdout="", stderr="")

    monkeypatch.setattr(pipeline, "run_test_agent", lambda *args, **kwargs: llm_tests)
    monkeypatch.setattr(pipeline, "run_generated_tests", fake_run_generated_tests)
    monkeypatch.setattr(pipeline, "run_simulation",
                        lambda: {"total_scenarios": 64, "passed": 64, "failed": 0, "results": []})

    process, report = pipeline.generate_consistent_tests({}, {}, "code", False, "initial")

    assert report["failed"] == 0
    assert written[-1] == reference_test_source()
    assert len(written) == 4, "three generated attempts, then the plan table"
    assert process.returncode == 0
    assert (tmp_path / "artifacts" / "test_navigation_rejected.py").exists()


def test_revision_that_scores_lower_is_reverted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["main.py", "--force-revision"])
    monkeypatch.setattr(pipeline.os, "chdir", lambda *args: None)
    monkeypatch.setattr(pipeline, "load_file", lambda path: "brief")
    monkeypatch.setattr(pipeline, "run_analyst", lambda brief: {"goal": "target"})
    monkeypatch.setattr(pipeline, "run_planner", lambda requirements: {"strategy": "safe"})
    monkeypatch.setattr(pipeline, "run_developer", lambda plan: FIXTURE_CODE)
    monkeypatch.setattr(pipeline, "run_developer_revision", lambda *args, **kwargs: plan_table_source())

    passing = ({"needs_revision": False}, {}, {"needs_revision": False, "safety_passed": True,
                                               "goal_completion_passed": True,
                                               "efficiency_passed": True}, 0)
    regressed = ({"needs_revision": True}, {}, {"needs_revision": True, "safety_passed": True,
                                                "goal_completion_passed": False,
                                                "efficiency_passed": False}, 1)
    rounds = [passing, regressed]
    monkeypatch.setattr(pipeline, "evaluate", lambda *args, **kwargs: rounds.pop(0))

    assert pipeline.main() == 0

    assert (tmp_path / "generated" / "navigation_logic.py").read_text(encoding="utf-8") == FIXTURE_CODE
    status = json.loads((tmp_path / "artifacts" / "pipeline_status.json").read_text(encoding="utf-8"))
    assert status["passed"] is True
    assert status["revisions_reverted"] == 1
    assert status["best_artifact"] == "initial"
    assert status["revision_attempts"] == 1
    assert status["plan_table_repairs"] == []


def test_non_compliant_developer_output_is_replaced(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "artifacts").mkdir()

    code, repaired = pipeline.ensure_plan_compliance(WRONG_CODE, "initial")

    assert repaired is True
    assert check_navigation(code) == []
    assert (tmp_path / "artifacts" / "initial_rejected_navigation.py").read_text(
        encoding="utf-8") == WRONG_CODE


def test_compliant_developer_output_is_kept(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "artifacts").mkdir()

    code, repaired = pipeline.ensure_plan_compliance(FIXTURE_CODE, "initial")

    assert repaired is False
    assert code == FIXTURE_CODE


def test_compiled_plan_table_matches_the_contract():
    source = plan_table_source()

    assert check_navigation(source) == []
    assert "decide_next_move" in source


def test_review_carries_measured_failures():
    report = {"results": [{"passed": False, "state": {"goal_ahead": True},
                           "expected": "FORWARD", "actual": "STOP"},
                          {"passed": True, "state": {}, "expected": "STOP", "actual": "STOP"}]}

    review = run_reviewer(report, offline=True)

    assert review["needs_revision"] is True
    assert review["measured_failures"] == [{"state": {"goal_ahead": True},
                                            "expected": "FORWARD", "actual": "STOP"}]
