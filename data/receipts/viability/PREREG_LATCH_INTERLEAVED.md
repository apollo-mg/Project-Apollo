# Pre-registration — is the latch VBR-specific? (interleaved, replicated)

**Registered 2026-09-10, before any arm ran.** Supersedes the sequential designs of 2026-09-09,
all of which were invalid: single-rep arms, run back-to-back, against a stochastic outcome.

## Why the previous design failed

Yesterday produced three attributions and retracted all three (checkpoints, backpressure,
idle-cache). The ledger showed **every latch before 22:31 and every run after 23:57 clean** —
start time predicted the outcome better than any manipulated flag. With one rep per condition run
sequentially, condition and time are perfectly confounded.

**The public claim this tests:** "pretty sure it's specific to your fork." That is currently
**unsupported** — every run to date used `buun-llama-cpp` *with* `-ctk vbr -ctv vbr --vbr-floor t2`,
so fork, VBR, IQ3_XXS, and RDNA4/ROCm 7.2 are perfectly confounded.

## Design

Three conditions, same fork, same model, same tasks — only the KV cache type differs:

| | condition | flags |
|---|---|---|
| **A** | VBR (status quo) | `-ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto` |
| **B** | quantised KV, no VBR | `-ctk q8_0 -ctv q8_0` |
| **C** | unquantised KV | `-ctk f16 -ctv f16` |

Both B and C verified to load at `-c 32768` before registering this.

- **Interleaved** A,B,C,A,B,C,A,B,C — never all reps of one condition together.
- **3 reps per condition**, 9 runs total.
- **12 tasks per run**, `--timeout-overhead 120` (180 s/task).
- **Early abort:** a run is declared LATCHED as soon as 3 consecutive `INFRA_ERROR` appear, then
  killed. Latched runs cost ~10 min instead of ~31.
- **GPU temperature, sclk/mclk and power sampled every 30 s to a per-run CSV** — the measurement
  `gpu-clock-benchmark-discipline` requires and which I failed to take all of yesterday, leaving
  the thermal confound untestable.
- Fresh server per run. No proxy anywhere (it is a known confound; the harness talks to :8090).

## Predictions

**P-F1: at least one of the three VBR reps latches. 70%.**
4 of 8 historical runs latched, but everything since 23:57 has been clean, so the base rate may
have shifted. *If FALSIFIED, the whole experiment is uninformative* — no latch anywhere means we
have lost the repro and must recover it before comparing anything.

**P-F2: the latch rate is higher under VBR (A) than under f16 (C). 55%.**
Barely above chance, deliberately. VBR is the obvious suspect and the log is full of
`VBR_RETIER_PREFLIGHT` / `vbr reset`, but yesterday taught that obvious suspects keep failing
their controls. With 3 reps per arm this can only detect a large effect; it cannot establish a
small one.

**P-F3: GPU junction temperature at latch onset is higher than in clean runs. 30%.**
Low because it is a fishing expedition, but the thermal confound is live and untestable without
this data, and collecting it costs nothing.

## What will NOT be claimed

3 reps per condition cannot support a rate claim. 0/3 vs 3/3 would be suggestive, not conclusive
(Fisher exact p = 0.1). Anything short of that is a pilot indicating whether a larger run is worth
the electricity. **Nothing goes to buun until an arm separates cleanly and is replicated.**
