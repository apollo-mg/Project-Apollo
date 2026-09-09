# RESULT: hermesbench dispatcher fix confirmed live (not just in offline re-scoring)

**Date:** 2026-09-08
**Hardware:** RX 9070 XT 16 GB (control plane), ROCm
**Model:** `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf`
**Server:** buun-llama-cpp `build_rocm`, flags verified from `/proc/<pid>/cmdline`:
`-ngl 99 -c 32768 -np 1 -fa on --kv-unified -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto --spec-type draft-mtp --reasoning-effort medium --min-p 0 --jinja`
**Bench:** `hermesbench run --all --toolsets all --timeout-overhead 300`, `hermes_sha f159e581c7afd22a5c94652c569e3859f1b994d2`
**Runs compared:** `qwen38_deploy_det02` (pre-fix, 61/61 complete) vs `qwen38_fixed_grader` (post-fix, 49/61 at analysis)

## Claim

The `toolcalls.py` dispatcher-normalisation fix converts the tasks it targets, and only those.

## Result: 6/6 targeted, 0 spurious

Per-task outcome diff on det02's nine graded failures:

| task | det02 | fixed_grader |
|---|---|---|
| t06_process_mgmt_t01_list | FAIL | **PASS** |
| t06_process_mgmt_t02_kill | FAIL | **PASS** |
| t06_process_mgmt_t03_poll | FAIL | **PASS** |
| t07_todo_plan_t01_plan | FAIL | **PASS** |
| t07_todo_plan_t02_update | FAIL | **PASS** |
| t07_todo_plan_t03_replan | FAIL | **PASS** |
| t03_patch_edit_t05_v4a | FAIL | INFRA_ERROR (not converted) |
| t10_memory_facts_t03_avoid_dup | FAIL | INFRA_ERROR (not converted) |
| t12_real_world_t02_error_recovery | FAIL | not reached |

All six failures in the `t06_process_mgmt` / `t07_todo_plan` families — exactly the families hit by the
`process`→`process_manage` and `todo`→`todo_list` renames in hermes-agent `e16ad33a9d` — flipped to PASS.
`t06_t04_pipeline` and `t06_t05_zombie` passed in **both** runs and still pass (they were never affected).

The three det02 failures **outside** those families did **not** flip to PASS. The fix is specific: it did not
launder unrelated failures into passes.

## The patch is exonerated as a cause of the run's infra errors

The patch runs at `runner.py:416-420`, downstream of the agent subprocess. Killed tasks show
`[hermesbench] run_agent timeout after 360s` in `run_agent.log` and `trace.jsonl` of **0 lines** —
the subprocess died before writing a trajectory, so `normalise_trace` was never reached on those tasks.
Grading code cannot cause a pre-grading timeout.

## What this receipt does NOT establish

- **The run's headline score is not usable.** `valid_pass_rate: 1.0` (`passed 34 / failed 0 / infra 15`) is an
  artifact: 11 tasks that PASSED in det02 became INFRA_ERROR here, hollowing out the denominator. Every task
  capable of failing after t07 was excluded. Do not quote 1.0, or 34/61, as a capability number.
- **The cause of those 11 timeouts is unresolved** and gets its own prereg. Ruled out so far: the patch
  (above), a wedged server (GPU 98%, actively generating mid-analysis), a stuck kernel
  (`hermes_kernel_p9qkz1d4` dates to Sep 4, 0% CPU, unrelated), and agent configuration
  (`run_agent.log` setup lines are byte-identical between runs — same 19 tools, same ~5,896-token first request).

## Retracted mid-analysis (recorded so it isn't repeated)

1. **"Decode collapsed to 19.5 t/s and stayed flat."** Wrong twice over. `tg` is llama-server's progress
   counter printed every ~3s *within one generation*; 40 "flat" samples were 40 progress prints of a single
   task. Then the correction was also wrong: `tg_3s` is a 3-second window, so `tg` does track instantaneous rate.
2. **"Decode is identical between runs (median 32.9 vs 33.3 t/s)."** RETRACTED — **survivorship bias**.
   `eval time ... tokens per second` is only emitted by *completed* requests. All 15 timed-out requests never
   emitted one, so the comparison structurally cannot observe the pathological requests. It compares det02
   survivors to fixed_grader survivors and shows only that survivors behave alike. The single measurement of a
   pathological request is the live `tg_3s ≈ 19.6` on task 119000 — ~40% below the survivor median.
3. **"`graphs reused`" is prompt-cache reuse.** It is HIP graph reuse. Unrelated field.

Three separate greps in this analysis matched the wrong field (`tg`, `reused`, and the earlier `cut -c1-185`
truncation of AFM-29). See FAILURE_MODES.md AFM-34.

## Files

- `/home/mark/projects/hermes-bench-tool-call/hermesbench/toolcalls.py` (the fix)
- `/home/mark/projects/hermes-bench-tool-call/hermesbench/runner.py:416-420` (call site)
- `hermesbench_fix/{toolcalls.py,runner.patch}` (copies in this repo)
