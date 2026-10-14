# Validation

The full pytest suite, all three original agent fixture checks, original navigation checks, and offline pipeline were tested. IR-SIM used the supplied navigation fixture and the original runner.

| Check | Result |
| --- | --- |
| Exhaustive boolean-state simulation | 64 passed, 0 failed |
| Original navigation checks | 14 passed, 0 failed |
| Pytest navigation and integration checks | 87 passed |
| Easy world | Goal reached in 150 steps |
| Medium world | Goal reached in 148 steps |
| Difficult world | Goal reached in 187 steps |
| Custom world | Goal reached in 193 steps |
| Goal success rate | 100% |
| Efficiency rate | 100% |
| Average steps | 169.5 |

All four runs reported `collision_or_done: false`.

The supplied visual scripts and original world files are unchanged. The original Analyst and Planner source files are unchanged.

Integration tests verify revision input handling and file saving with a mocked model response, plus retry handling for HTTP 503 and reviewer JSON parsing, schema requests, and invalid-response retries. Test Agent checks also cover preserving valid bare Python output and retrying invalid test source. Live Qwen generation, review, and revision have not been verified in this environment.

To verify the online pipeline locally, start Ollama with `qwen3:8b` installed and run:

```bash
python run_all_checks.py
```

Check the new `artifacts/pipeline_status.json`, reports, and `trace.log`. Offline results do not establish that the online pipeline passes.

The full pytest suite uses importlib mode to avoid duplicate module names in the original and legacy checks. Failed generated pytest output is included in developer revision notes. A stale revision file cannot mark a new run as verified.
