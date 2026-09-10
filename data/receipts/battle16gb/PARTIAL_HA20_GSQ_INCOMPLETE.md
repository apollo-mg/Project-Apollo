# INCOMPLETE — HA-20 on Qwen3.8-27B GSQ-RCO IQ3_XXS (run stopped at scenario 5 of 40)

**2026-09-03. THIS IS NOT A RESULT.** The run was stopped externally partway through the
first of two arms. 5 of 20 scenarios in arm 1; arm 2 (Dirk template) never started.
HA-20's own noise floor is ~15% of scenarios (`HA20_SAMPLING_ARMS.md`), so five cells
cannot be compared to anything. Recorded only so the partial is not re-derived or,
worse, quoted.

Setup: RX 9070 XT, `tq_head f97400563`, `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` (3.05 bpw),
`-c 24576`, f16 KV, `-fa on`, `-np 1`, temp 0, K=1, runner `run-scenarios.mjs` unmodified,
endpoint pinned to `127.0.0.1:8094` (never openrouter). Healthy in 10s, 84% VRAM,
one server asserted.

| scenario | stock-template arm | Bonsai-27B (2026-07-29 baseline) |
|---|---|---|
| HA-01 memory replace | FAIL 10 | PASS 100 |
| HA-02 memory capacity | FAIL 20 | PASS 100 |
| HA-03 injection reject | PASS 100 | PASS 100 |
| HA-04 recall prior fix | FAIL 20 | (bistable in baseline) |
| HA-05 repair failing test | FAIL 0 | — |
| HA-06 … HA-20 | not run | — |

**Arm 2 — the Dirk/froggeric template on identical weights — is the one that matters**
and did not run. The stock template defaults to `xhigh` reasoning effort (AFM-23), which is
the condition Dirk exists to change, so arm 1 alone cannot separate "3.05 bpw is too low for
agentic work" from "xhigh thinking blows the scenario budget".

To resume: `scratchpad/ha20_gsq.sh` is fixed and idempotent (verifies a clean slate, tears
down by PID with SIGKILL escalation). ~12 min per arm.

## Teardown bug found and fixed during this run

The first attempt aborted both arms on its own "exactly one llama-server" assertion. Two
faults, both mine:

1. `pkill -x llama-server` **returns 0 while leaving the process alive.** After a turbo run
   this build hangs in shutdown — VRAM is released, the process stays in `S<l` indefinitely.
   The previous run's server was still resident, reparented to `systemd --user`. SIGTERM did
   not clear it after 40s; SIGKILL did.
2. The abort path did `return 1` *before* teardown, so each failing arm leaked its own
   server on top of that.

Fixed: teardown escalates TERM -> KILL and gates on `ps -eo comm | grep -c '^llama-server$'`
reaching 0, not on a return code; every failure path tears down first; the script refuses to
start unless the count is already 0.

That is the seventh guard this campaign that reported success while leaving the job
undone — same shape as the six in the compaction note.
