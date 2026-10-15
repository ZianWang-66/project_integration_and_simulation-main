# Integration and Simulation

A navigation agent pipeline with generated tests, simulation, IR-SIM benchmarks, review, and code revision.

## Setup

Create the project virtual environment, then install the pinned dependencies into it.

Windows (PowerShell):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `py` is unavailable on Windows, replace `py -3` with the path to a Python 3 interpreter, or use `python -m venv .venv` when `python` is already on `PATH`. `.venv/` is git-ignored. After activation, run every command below with the environment active so `python` resolves to the environment interpreter.

Install the model used by the online agents:

```bash
ollama pull qwen3:8b
```

Start Ollama if it is not already running, then run:

```bash
python main.py --force-revision
```

The pipeline runs the Analyst, Planner, Developer, Test Agent, simulation, simulation reviewer, IR-SIM benchmark, and benchmark reviewer. A revision is saved as `generated/navigation_logic_revised.py` and applied to `generated/navigation_logic.py` before testing again. `--force-revision` requests one revision even when the initial run passes.

Every IR-SIM world drives in its own window (robot, obstacles, goal, trajectory) and holds the final frame for three seconds, so `python main.py` doubles as the demo: it prints each world as it starts and reports goal, steps, collisions and clearance when that world finishes. Add `--headless` to run the four worlds without windows (faster, intended for batch verification).

The default allows up to three revisions; `--max-revisions` changes the limit. A failed pipeline returns exit code 1. Ollama requests disable thinking and retry HTTP 429 or 503 up to twice. Reviewers request structured JSON, validate the response, and retry invalid responses up to three attempts. Invalid raw responses are saved under `artifacts/`. The Test Agent retries invalid Python output up to three attempts and saves its latest raw response to `artifacts/test_agent_raw_output.txt`.

## Offline Run

```bash
python main.py --offline
```

Offline mode replays the supplied fixtures and runs real IR-SIM benchmarks. It does not call Qwen or perform an LLM revision. The exhaustive simulation uses the original plan's direction priorities; online generated tests also check the current requirements and plan.

## Visual Simulation

```bash
./run_visual.sh irsim_worlds/world_easy.yaml
./run_visual.sh irsim_worlds/world_medium.yaml
./run_visual.sh irsim_worlds/world_difficult.yaml
./run_visual.sh irsim_worlds/world_custom.yaml
```

On Windows, use `python test_irsim_with_agent.py` followed by the world path. `world_difficult.yaml` is a copy of the supplied `world_hard.yaml`. The supplied visual scripts and original world files are unchanged.

## Reports

Results are saved in `artifacts/`, including `simulation_report.json`, `irsim_benchmark_report.json`, `simulation_review.json`, `benchmark_review.json`, and `pipeline_status.json`. `trace.log` records progress. Reports for each evaluation round are copied to `artifacts/initial/` or `artifacts/revision_1/`.

An efficient IR-SIM run reaches the goal within 200 steps. The maximum is 300 steps. The supplied `collision_or_done` field indicates a terminal condition and does not distinguish every possible cause.

## Simulation Safety

`test_irsim_with_agent.py` is the rig around the generated logic. It measures the six flags against the real obstacle polygons (buffered by the robot radius plus a 0.25 m margin) and the arena boundary, and it commands the robot through a safety supervisor:

- LEFT and RIGHT rotate in place, so a dodging manoeuvre cannot translate the robot into anything.
- FORWARD is only issued when a corridor check proves the next step stays clear of every obstacle and of the walls.
- While the front corridor is blocked the robot commits to one turning side instead of oscillating, and only resumes goal seeking once that corridor is clear again. A stall watchdog forces a decisive rotation when a run stops making progress.

Every report therefore carries `collisions`, `safety_overrides`, `escape_maneuvers` and `min_clearance` next to the original fields. `collision_or_done` keeps its meaning: the run ended in a stop or arrival rather than a clean goal arrival.

`matplotlib_compat.py` guards a flaky dependency: on CPython 3.14 the docstring introspection matplotlib runs while building its class hierarchy can raise `RuntimeError: internal error in regular expression engine`, which used to abort IR-SIM before the robot moved. The runner imports the guard before IR-SIM, and `benchmark_irsim.py` retries a world up to three times in a fresh interpreter.

## Pipeline Verdicts

`run_simulation` checks all 64 boolean states against the plan's decision table and is the deterministic reference. When the Test Agent's file contradicts that table it is regenerated, and if it keeps disagreeing it is replaced by the deterministic test file built from the plan, so the pipeline does not revise correct code because a generated test was wrong.

A revision is kept only when it scores at least as well as the current best round (safety, goal completion, efficiency, pytest). A revision that scores lower is reverted, recorded as `revisions_reverted` in `artifacts/pipeline_status.json`, and the verified artifact stays in `generated/navigation_logic.py`.

The Developer Agent checks its own output against the plan's decision table and retries with the wrong states explained. If the code still does not implement the table for every one of the 64 boolean states, the pipeline saves the model output as `artifacts/<round>_rejected_navigation.py` and compiles the plan's table itself (`navigation_spec.plan_table_source()`), recording the round in `plan_table_repairs`. The artifact under test therefore always implements the plan.

`generated/` holds run artifacts, so `python -m pytest -q` collects `tests/` only. The pipeline runs `generated/test_navigation.py` explicitly and saves the output to `artifacts/<round>_pytest.txt`.

## Complete Verification

```bash
python run_all_checks.py
```

This runs the original agent fixture checks, original navigation checks, full pytest suite, offline pipeline with four real IR-SIM worlds, and finally the online Qwen pipeline with a forced revision and up to three revision attempts. The worlds show their windows exactly as in a normal run; add `--headless` for a windowless verification. It stops on any failure and saves `artifacts/all_checks_report.json` and `artifacts/all_checks_output.log`.

```bash
python run_all_checks.py --offline
```

Offline verification omits the live Qwen stage. Passing offline verification does not mean the online stage has passed.

For individual checks:

```bash
python tests/test_generated_navigation_logic.py
python -m pytest -q
```

See `VALIDATION.md` for measured results. This repository combines the original project and integration template. If the course requires submission in a different original project repository, copy these changes there.
