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

---

## SCORING (2026-09-10 12:19, all 9 runs complete)

| run | KV | pattern | capped gens | vbr resets | resets gone bad |
|---|---|---|---|---|---|
| A1 | VBR | `.........I.I` | 1 | 11 | 1 |
| A2 | VBR | `..III` (aborted early) | 3 | 5 | 3 |
| A3 | VBR | `...........I` | 1 | 11 | 1 |
| B1 B2 B3 | q8_0 | all `............` | **0** | 0 | 0 |
| C1 C2 C3 | f16 | all `............` | **0** | 0 | 0 |

**VBR 3/3 runs affected. Non-VBR 0/6. Fisher one-tailed p = 0.0119.**
**5/5 degenerate generations followed a `vbr reset`. 5/27 resets (18.5%) went bad.**

**P-F1 (70%) CONFIRMED** — the repro was not lost; all three VBR reps failed.
**P-F2 (55%) CONFIRMED** — latch rate is higher under VBR than f16, at the largest possible
separation for this design (3/3 vs 0/3).
**P-F3 (30%) FALSIFIED** — power does not track failure. f16 spent **11.9%** of seconds above the
374 W hard cap and was clean; VBR spent **2.9%** and failed every run. Excursion rate is
*anti*-correlated with failure.

### Design notes that mattered

Interleaving A,B,C,A,B,C,A,B,C was what made this readable. Yesterday's sequential single-rep arms
produced three attributions and three retractions; the same data collected in blocks would have
been confounded with time again. The early-abort on 3 consecutive INFRA saved ~20 min on A2 alone.

### Caveat that remains

Everything here is one card (gfx1201), one model, one quantisation, one fork. The claim supported
is "VBR fails where q8_0 and f16 do not, on this hardware" — not that VBR is broken in general.

---

## Pre-registration — does buun's master fix it? (logged before building)

Our build is `3823c9eb6`; master is `d0f82fd41`, **10 commits ahead**. Two are on-point:

- **`c685ea741` cuda: fix asymmetric TCQ fused codebooks** — touches `fattn-mma-f16.cuh` and ships
  `tests/test-cuda-tcq-asym-codebooks.cpp`. **Verified reachable on our card:**
  `amd_wmma_available(cc)` returns true for RDNA4, and `AMD_WMMA_AVAILABLE` is defined under
  `GGML_USE_HIP && (RDNA4 || RDNA3)`. We run `-fa on`, so gfx1201 executes this path.
- **`28027a349` server: restore VBR cache across idle slot handoffs** — touches the slot-handoff
  path that our `vbr reset` correlation implicates.

### Design

Built in a **separate git worktree** at `origin/master` so the `3823c9eb6` binary and the local
`test-backend-ops.cpp` RDNA4 cases both survive. Identical cmake config
(`GGML_HIP=ON, AMDGPU_TARGETS=gfx1201, Release, GGML_NATIVE=ON, LLAMA_CURL=ON`).

**Interleaved OLD/NEW, 3 reps each** — not 3 old then 3 new. Same reason as before.

### Predictions

**P-M1: on master, VBR runs produce zero capped generations. 60%.**
`c685ea741` is a correctness fix in a path this card executes, and a codebook bug would corrupt
attention exactly as observed. Held at 60% because five hypotheses have died this week and the
fault may live elsewhere entirely.

**P-M2: `test-cuda-tcq-asym-codebooks` passes on gfx1201. 70%.**
*If it FAILS this is the more valuable outcome* — it would mean the fix is correct on NVIDIA but
not on AMD WMMA, which would explain why buun cannot reproduce, and only this machine can find it.

**P-M3 (positive control): OLD-build VBR runs in the same session still fail. 85%.**
Without this, a clean NEW result is uninterpretable. This is the control whose absence invalidated
the entire P-D2 experiment last night; it is not optional.

Joint reading: NEW clean + OLD fails → master fixes it. Both fail → fix does not cover this bug or
this hardware. Both clean → we lost the repro again; nothing is concluded.

---

## Pre-registration — localising the fault with env vars (logged before running)

Reading `fattn.cu` on master surfaced two runtime switches that let us localise this **without a
rebuild**, plus a likely mechanism.

**Mechanism hypothesis — stale TCQ codebooks in constant memory.** The fused path loads codebooks
once per device and never reloads:
```c
static bool tcq3_fused_loaded[GGML_CUDA_MAX_DEVICES] = {};
if (!tcq3_fused_loaded[device] || tcq_hot_f) { tcq3_fused_loaded[device] = true; turbo_tcq_load_kv_decode(); }
```
If a `vbr reset` re-tiers K/V, the resident codebook may belong to a different tier than the one
now being decoded. This predicts every observation: VBR-only (nothing else re-tiers), ~18.5% of
resets (only when the tier actually changes to one needing a different codebook), **recovery
between failures** (A1 went `.........I.I` — if tiers move back the cached codebook is correct
again), and clearing on restart.

Also noted: `turbo_fused_asym_pair()` covers only *adjacent-tier* pairs, and buun's own comment
says non-adjacent straddles "DO occur live"; the AMD branch is guarded by `amd_wmma_available()`
with the comment "**trying** D=128 AND D=256 … after lifting the upstream DKQ<=128 cap".

### Arms (all VBR, old build unless stated), interleaved ×3

| arm | change |
|---|---|
| OLD | `3823c9eb6`, stock — positive control |
| NEW | `origin/master d0f82fd41`, stock |
| FUSED0 | old + `GGML_TURBO_MMA_FUSED=0` (disables the fused turbo MMA path) |
| HOT | old + `TURBO_TCQ_HOTSWAP=1` (forces codebook reload every dispatch) |

### Predictions

**P-E1: FUSED0 produces zero degenerate generations. 70%.** It disables the suspect path outright;
if the fault lives there this must work. Not 90% because the fault may be upstream of dispatch.
**P-E2: HOT produces zero degenerate generations. 50%.** Only if *staleness* specifically is the
mechanism, rather than wrong codebook content or the asym-pair gap.
**P-E3 (positive control): OLD still fails. 85%.** Without it nothing else is readable.
**P-M1 restated: NEW produces zero. 60%.**

Joint: FUSED0 clean + HOT clean → stale codebooks. FUSED0 clean + HOT fails → fused kernel, but
not staleness. Both fail → fault is not in the fused path. OLD clean → repro lost, all void.

---

## SCORING — localisation experiment (2026-09-10 14:55, 12 runs complete)

| arm | runs affected | capped gens | vbr resets | bad-per-reset |
|---|---|---|---|---|
| OLD `3823c9eb6` | 2/3 | 6 | 27 | 22.2% |
| NEW `origin/master d0f82fd41` | 2/3 | 5 | 33 | 15.2% |
| **FUSED0** (`GGML_TURBO_MMA_FUSED=0`) | **0/3** | **0** | 33 | **0.0%** |
| **HOT** (`TURBO_TCQ_HOTSWAP=1`) | **0/3** | **0** | 33 | **0.0%** |

Stock arms 11/60 resets bad; flagged arms 0/66. P(0 in 66 at the 18.3% stock rate) ≈ 1.7e-6.

**P-E1 (70%) CONFIRMED.** Disabling the fused turbo MMA kernel eliminates the fault entirely.
This localises it to the fused path, on a build predating buun's codebook fix.

**P-E3 (85%) CONFIRMED.** OLD still failed, so the repro was intact and the comparison is readable.

**P-M1 (60%) FALSIFIED. Master does not fix it.** 5 capped generations over 33 resets, 15.2%
against OLD's 22.2% — a reduction well inside noise at this n, not an elimination. `c685ea741`
("cuda: fix asymmetric TCQ fused codebooks") does not close this on gfx1201.

**P-E2 (50%) CONFIRMED — and this contradicts the author's expectation.**
buun stated: *"TURBO_TCQ_HOTSWAP won't help, that flag is for reloading optional external codebook
files."* Empirically `TURBO_TCQ_HOTSWAP=1` eliminated the fault as completely as disabling the
fused kernel: 0 of 33 resets. We are not claiming to know why. The observation is only that the
flag, whatever its intent, gates `turbo_tcq_load_kv_decode()` / `turbo2_tcq_load_kv_decode()`
inside the fused dispatch path:
```c
if (!tcq3_fused_loaded[device] || tcq_hot_f) { tcq3_fused_loaded[device] = true; turbo_tcq_load_kv_decode(); }
```
Forcing that reload every dispatch removes the failure. Whether that is because constant-memory
codebook state was stale, or because the extra load perturbs timing, this experiment cannot say.

### Design note

Rep 3 was clean in **all four arms**, including OLD and NEW. The trigger remained stochastic and
rep-3 conditions were quiet. Interleaving is what preserves the comparison: within reps 1 and 2,
OLD and NEW failed while FUSED0 and HOT did not, under identical conditions minutes apart. A
blocked design run OLD-OLD-OLD then FUSED0-FUSED0-FUSED0 would have produced the same numbers and
been uninterpretable.
