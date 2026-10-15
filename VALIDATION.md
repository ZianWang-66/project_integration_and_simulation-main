# Validation

The full pytest suite, all three original agent fixture checks, the original navigation checks, the offline pipeline and the online Qwen pipeline were run on this machine (Windows, CPython 3.14, IR-SIM 2.12, Ollama `qwen3:8b`).

| Check | Result |
| --- | --- |
| Exhaustive boolean-state simulation | 64 passed, 0 failed |
| Original navigation checks | 14 passed, 0 failed |
| Pytest suite (`tests/`) | 40 passed |
| Easy world | Goal reached in 103 steps, 0 collisions |
| Medium world | Goal reached in 95 steps, 0 collisions |
| Difficult world | Goal reached in 122 steps, 0 collisions |
| Custom world | Goal reached in 134 steps, 0 collisions |
| Goal success rate | 100% |
| Efficiency rate | 100% |
| Average steps | 113.5 |
| Smallest obstacle clearance kept | 0.264 m |
| `run_all_checks.py` (offline and online stages) | All checks passed |

Every world reports `collisions: 0`, `collision_or_done: false` and `termination: goal_reached`. Each world also drives in its own window when the pipeline is run without `--headless`: the demo holds the final frame for three seconds and the process returns on its own (it never blocks in a GUI main loop).

`artifacts/pipeline_status.json` reports `passed: true` for both `main.py --offline` and the online run (`main.py --force-revision --max-revisions 3`, `llm_revision_verified: true`).

The supplied visual scripts and original world files are unchanged. The original Analyst and Planner source files are unchanged.

The navigation runner keeps the robot collision-free: the six flags are measured against the real obstacle polygons (buffered by the robot radius plus a 0.25 m margin) and the arena boundary, LEFT/RIGHT are executed as rotations in place, FORWARD is only issued when the next step is provably clear, and a dodge keeps turning in one direction until the front corridor is clear. `matplotlib_compat.py` guards the flaky CPython 3.14 regex failure inside matplotlib's import, which used to abort IR-SIM at random, and `benchmark_irsim.py` retries a world up to three times.

Integration tests verify revision input handling and file saving with a mocked model response, plus retry handling for HTTP 503 and reviewer JSON parsing, schema requests, and invalid-response retries. Test Agent checks also cover preserving valid bare Python output and retrying invalid test source. `tests/test_simulation_safety.py` covers the corridor checks, the supervisor, the subprocess retry and the window/headless switch; `tests/test_pipeline_guards.py` covers the Developer Agent's plan self-check, the generated-test/plan agreement, the plan-compilation fallback and the "keep the best artifact" revision rule. Live Qwen generation, review, and revision were exercised locally with Ollama and `qwen3:8b`.

To verify the online pipeline locally, start Ollama with `qwen3:8b` installed and run:

```bash
python run_all_checks.py
```

Check the new `artifacts/pipeline_status.json`, reports, and `trace.log`. Offline results do not establish that the online pipeline passes.

`qwen3:8b` does not transcribe the plan's 64-state decision table reliably (its output usually disagrees in one or two states). The Developer Agent therefore checks its own output against the table and retries with the wrong states explained, and the pipeline replaces an output that still disagrees with `navigation_spec.plan_table_source()`, recording the round in `plan_table_repairs`. The artifact under test always implements the plan.

The full pytest suite uses importlib mode to avoid duplicate module names in the original and legacy checks, and collects `tests/` only, because `generated/` holds run artifacts. Failed generated pytest output is included in developer revision notes. A stale revision file cannot mark a new run as verified.
