# Result — buun's `a334fc01e` stops VBR's post-reset runaways on gfx1201; its parent does not

**Date:** 2026-09-11.
- **Prereg:** `PREREG_LATCH_INTERLEAVED.md`, the section "does `a334fc01e` fix it?" and its
  amendment. Both were committed before the data they govern was read.
- **Data:** `fix-ab/` (`driver.log`, `server_*.log`, `gpu_*.csv`).
- **Driver:** `fix-ab/fix_ab.sh`. **Counting:** `fix-ab/runaways.py`.

**Setup.**
- **Card:** RX 9070 XT (gfx1201), 330 W cap, `vm_update_mode` -1. That resolves to CPU page-table
  updates for compute on this large-BAR card.
- **Model:** GSQ-RCO Qwen3.8-27B IQ3_XXS.
- **Flags:** `-ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto -c 32768`, fused turbo MMA on, no env
  vars, no boot flags.
- **Workload:** hermesbench, 12 tasks, 180 s per task, abort after 3 consecutive INFRA_ERROR.
- **Order:** interleaved, with arm order rotating each rep.

## Result

A *runaway* is a generation that reaches 1,000 tokens and either completes at the 4096 cap or is
cancelled while still generating (the amendment rule). The *cap rule* is the original: completions
at 4096.

| arm | runs | resets | runaways | of which right after a reset | cap rule | runs latched | median decode |
|---|---|---|---|---|---|---|---|
| **FIX** `a334fc01e` | 3 | 33 | **0** | 0 | 0 | 0 of 3 | 24.5 t/s |
| **PARENT** `2fd7e523b` | 3 | 22 | **6**, all cut off by the timeout | 6 | **0** | 2 of 3 | 24.6 t/s |
| **OLD** `3823c9eb6` (positive control) | 3 | 31 | **4**: 3 at the cap, 1 cut off | 3 | 3 | 1 of 3 | 26.8 t/s |

| run | resets | runaways (after a reset) | cap rule |
|---|---|---|---|
| OLD1 | 11 | 0 | 0 |
| PARENT1 | 5 | 3 (3) | 0 |
| FIX1 | 11 | 0 | 0 |
| PARENT2 | 11 | 0 | 0 |
| FIX2 | 11 | 0 | 0 |
| OLD2 | 11 | 1 (0) | 0 |
| FIX3 | 11 | 0 | 0 |
| OLD3 | 9 | 3 (3) | 3 |
| PARENT3 | 6 | 3 (3) | 0 |

## Pre-registered verdicts

- **P-X1 (85%): OLD produces at least one degenerate generation. CONFIRMED** under both rules (cap rule
  3, runaway rule 4).
- **P-X2 (70%): FIX produces none. CONFIRMED** under both rules: 0 in 33 resets.
- **P-X3 (70%): PARENT produces at least one.**
  - **Cap rule: FALSIFIED** (0).
  - **Runaway rule: CONFIRMED** (6).
  - **Which counts:** the amendment names the runaway rule as the valid one where the two disagree. It
    was registered after rep 1 but before reps 2 and 3 were read, and **PARENT3 alone, which ran
    after it was registered, has 3.**
- **Joint reading, as registered:** OLD fails, PARENT fails, FIX clean. **The fix commit cures it on
  gfx1201,** not the other 175 commits in master.

## Why the cap rule missed PARENT

Master decodes this model about 9% slower than `3823c9eb6` on this card: median 24.5 vs 26.8 t/s,
same flags, same session. FIX and PARENT are equally slow, so the slowdown comes from the other 175
commits, not the fix.

- **At 24.5 t/s:** a runaway needs about 167 s for 4,096 tokens, plus the ~17 s re-prefill a reset
  triggers. That is about 184 s, past the harness's 180 s timeout, so the request is cancelled before
  it reaches the cap.
- **At 26.8 t/s:** it takes about 169 s and completes at the cap.

## How strong

- **Per reset:**
  - FIX 0 of 33 vs PARENT 6 of 22: **P = 0.003** (hypergeometric, margins fixed).
  - 0 of 33 at this session's non-FIX rate (9 of 53): 0.002.
  - FIX vs OLD alone (3 of 31): 0.11.
  - **Resets are not independent,** though: runaways cluster inside the runs that latch.
- **Per run** (the safer unit): FIX 0 of 3 runs affected vs 3 of 6 for the others, **P = 0.24.**
- **So: strong per reset, weak per run, from one session of nine runs.**
- **What it agrees with:**
  - the mechanism: buun's standalone repro (address reuse after remaps), and what this commit changes
    (a TLB invalidation after same-address VBR remaps, plus a NaN-safe recurrent reset)
  - the localisation, where FUSED0 and HOTSWAP were each 0 of 33

## The retroactive check (from the amendment)

Rescanned with the runaway rule, every earlier published count stands:
- FUSED0: 0 of 33
- q8_0 and f16: 0
- master `d0f82fd41`: 5 of 33
- localisation OLD: 6 of 27
- interleaved VBR: 5 of 27

**HOT gains one ambiguous generation:** at least 1,000 tokens, cut off by the timeout, with no reset
before it. HOT's "0 bad resets" stands. OLD2 in this session has one case of the same kind.

## Also measured

- **The positive control was weaker than in the localisation.** OLD failed 1 of 3 runs (3 bad resets in
  31) against 2 of 3 (6 in 27) there. It still failed, which is what makes FIX's zero readable.
- **The fix needs no boot flag:** `vm_update_mode` stayed -1 throughout. The boot-flag test
  (`amdgpu.vm_update_mode=0`) is not needed to use the fix. It would still show whether the CPU
  page-table path is the trigger.

## Caveats

- **Scope:** one card, one model, one quant, one session.
- **Per-run evidence is weak** (P = 0.24), and the per-reset figure assumes independence.
- **The runaway rule was registered after rep 1.**
