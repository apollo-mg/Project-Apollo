# HermesBench on Pascal — 55/61, and two of the six failures are the harness, not the model

**Date:** 2026-07-26 · **Benchmark:** [am423/hermes-bench-tool-call](https://github.com/am423/hermes-bench-tool-call) @ `10bf4c6`
**Topology:** control-plane desktop drives (hermes-agent lives there); **.73** dual Tesla P100
serves at 1063 MHz / 150 W. `hermes-agent` @ `07e97d2f5`.
**Model:** `DavidAU-Fable-Fusion-711-MTP-Q6_K` (Qwen3.6-35B-A3B derivative), buun_vbr build,
VBR KV cache, `--spec-type draft-mtp --spec-draft-n-max 2`
**Command:** `--all --toolsets all --timeout-overhead 300`
**Wall clock:** 2 h 49 m (03:36 → 06:26), 2.82 h of task time, median task 140 s, max 360 s.

## Headline

| | |
|---|---|
| **PASS** | **55 / 61** |
| FAIL | 4 |
| INFRA_ERROR | 2 |

Perfect scores in 10 of 13 categories: terminal smoke 5/5, file read 6/6, patch 5/5,
search 5/5, write 5/5, process 5/5, todo 3/3, error recovery 3/3, real world 3/3,
**HumanEval micro 10/10**.

## The six non-passes, classified

| task | status | score | why |
|---|---|---|---|
| `t09_web_lookup/t01_search` | FAIL | **1.0** | "model did not use web_search" |
| `t09_web_lookup/t02_extract` | INFRA_ERROR | 0.0 | timeout at 360 s |
| `t09_web_lookup/t03_no_result` | FAIL | **1.0** | "model did not use web_search" |
| `t10_memory_facts/t02_recall` | FAIL | **1.0** | "model did not use memory" |
| `t10_memory_facts/t03_avoid_dup` | FAIL | **1.0** | "model did not use memory" |
| `t08_execute_code/t02_pandas` | INFRA_ERROR | 0.0 | timeout at 360 s |

**Every FAIL has `score=1.0` and `exit=0`** — the model produced correct output and was failed
on the *tool-usage* criterion, which is the benchmark working as designed. But whether that
criterion is legitimate differs by category, and the difference is a dependency:

### t09_web_lookup 0/3 — INVALID, the tool was never loaded

The `web` toolset is in hermes-agent's missing-requirements list on this box. Verified against
the actual loaded-tool list for `t09/t01`: the only search tools present were **`search_files`
and `session_search`** — local file and session search. `web_search` and `web_extract` were
**never given to the model**.

So the model was scored FAIL for not calling a tool it did not have, and produced a correct
answer anyway. Three of six failures are a missing dependency on the host.

### t10_memory_facts 1/3 — VALID

`memory` **was** in the loaded tool list. The model had it, chose not to use it, and answered
correctly from context instead. That is a genuine tool-selection failure and exactly what this
benchmark exists to measure. Legitimate.

### Adjusted score

Excluding the three tasks the harness could not actually run:

**55 / 58 = 94.8 %**

## The timeout finding — the reason this receipt exists

The first smoke run scored **0.0 / INFRA_ERROR** on a task that is literally
*"run `echo hello-hermesbench` and report the output."*

```
Request size: 2 messages, ~3,504 tokens        <- hermesbench's own estimate
n_tokens = 12288 ... t = 82.60 s @ 148.76 t/s  <- what .73 actually processed
[hermesbench] run_agent timeout after 90s
```

**29 tool schemas inflated a 3.5 k-token request to ~13 k tokens.** At the P100's ~148 tok/s
prompt-processing rate that is **83 seconds before the first output token**, against a 90 s
task timeout (60 s declared + 30 s default overhead). The model was cancelled with ~7 seconds
of budget to think.

Same model, same task, same server, `--timeout-overhead 300`: **PASS, score 1.0, 129.6 s.**

Both runs are preserved here as `smoke01_timeout_failure.json` and `smoke02_timeout_pass.json`.

**Generalisation:** this benchmark's default timeouts assume prompt-processing throughput that
Pascal-class hardware does not deliver once a realistic tool set is in context. Anyone running
it on older GPUs will collect INFRA_ERRORs that read as model incapability. The estimate the
harness prints (~3.5 k tokens) does not count tool schemas, so the discrepancy is invisible
from the harness side — you have to read the server log to see it.

Two tasks still hit the raised 360 s ceiling (`t08 pandas`, `t09 extract`); a further increase
is warranted for compute-heavy tasks.

## Why the tool-schema cost matters beyond timeouts

`--toolsets all` deliberately overrides each task's declared `allowed_tools` (the echo task
declares only `terminal`) so that *selecting* the right tool is part of what is measured. That
is a defensible design. It also means every task carries 29 tool schemas in context — and
`data/receipts/thinking-suppression-2x2/` established that **tool-schema presence combined with
a system persona collapses reasoning ~2.5×**. An agent benchmark run at `--toolsets all` is
therefore operating squarely inside the suppression regime, on every task.

## Setup notes (reproducing this)

- **Do not run `install.sh`** — it invokes `sudo pacman -S --noconfirm` (and apt/dnf/brew
  equivalents) unattended. `scripts/bootstrap.sh` does the venv + editable install with no
  system changes.
- hermesbench requires `<hermes-agent>/.venv`. This box's hermes-agent already had a working
  venv at `venv/` (the live gateway runs from it). Resolved with a symlink `.venv -> venv`,
  which is gitignored, leaves the tree clean, and does not disturb the running gateway.
- **`--use-hermes-config` is a footgun here.** It resolved to **`grok-composer-2.5-fast`** — a
  paid cloud endpoint — despite `~/.hermes/config.yaml`'s `model` block pointing at
  `http://10.0.0.73:8082/v1`. Use explicit `--model` + `--base-url`. Caught by `--dry-run`.
- Task execution is properly isolated: fresh tmux session per task, per-task worktree, isolated
  `$HOME`, ulimits, optional network unshare.

## Scope limits

- One model, one run, no repeats (`--n-runs 1`), so no variance estimate per task.
- Hardware telemetry (GPU power/temp, joules-per-token, thermal AUC) is **invalid in this
  topology** — it samples the machine running the benchmark (AMD desktop), not the machine
  running the model (.73). Those metric groups should be ignored here.
- The `web` toolset absence is a property of this host, not of the benchmark.

## Files

| file | what |
|---|---|
| `summary.json` | full 61-task result |
| `smoke01_timeout_failure.json` / `smoke02_timeout_pass.json` | the timeout finding, both sides |
| `full01.log` / `run_full.sh` | driver and log |
