# Prereg — why MTP buys EXL3 less: the micro-batch cost curve (EXL3 campaign, test 4, ledger O5)

**Written 2026-09-12 ~16:25, before any sweep data.**

## Question

Test 1 measured MTP giving EXL3 **1.24×** and GGUF **1.69×**, at identical draft acceptance (0.693 vs
0.688). Since the same fraction of drafts is accepted, the difference has to be in what a verify step
costs. **But test 1 measured drafting and verification together, so that is an inference, not a
measurement.** This test measures the cost directly.

With `--draft-max 3`, each speculative step evaluates up to 4 rows in one matmul. Both formats have a
small-batch kernel that covers it:
- **GGUF:** MMVQ, at up to `MMVQ_MAX_BATCH_SIZE` = 8 rows (`mmvq.cuh:3`).
- **EXL3:** the int8 path, at up to `MAX_M` = 8 (`exl3-gemv-int8.cuh:30`, whose comment says it "covers
  speculative verify batches (draft-max 3 default, up to 7)").

**So neither falls off its fast path at 4 rows.** The open question is how each kernel's cost scales with
rows.

## Setup

- **Node:** `.73`, both P100s, wake proxy paused with a dead-man timer. The orchestrator
  (`orchestrate_mtp.sh`) waits for test 3 to finish before taking the node.
- **Tool:** `llama-bench` from the same build as every other test (buun `9ae8f0f40` plus the e8m0
  guard), built there as an extra target. Its `build:` line must read `9ae8f0f40`.
- **One process per weights format,** so the model loads once and every ubatch setting reuses it.
- **Flags:** `-ngl 99 -sm layer -fa on -ctk f16 -ctv f16 -p 64 -n 8 -ub 1,2,4,8,16 -r 3 -o json`.
- **`-sm layer`, not tensor.** llama-bench has no tensor split mode. Test 1's asymmetry was measured
  under tensor split, but the kernel question is the same under layer split, and tensor split would add
  a per-step all-reduce that is not what this test is about.

| arm | weights |
|---|---|
| X | turboderp EXL3 4.00bpw |
| Q | the daily driver's Q6_K |

## Measures

- **pp64 throughput at each ubatch,** as llama-bench reports it.
- **Amortization ratio `A(m) = t/s(pp64, ub=m) ÷ t/s(pp64, ub=1)`.**
  - `A(m) = m` means the kernel reads its weights once per batch: fully amortized.
  - `A(m) = 1` means every row costs a full pass over the weights.
- **tg8 at each ubatch is the control.** Decode is one row whatever the ubatch, so it must stay flat.

## Predictions

| id | prediction |
|---|---|
| P-M0 | **Control.** For each arm, tg8 varies by less than 10% across the five ubatch settings. If not, the node is noisy and everything below is descriptive |
| P-M1 | GGUF amortizes: A(4) ≥ 2.5 |
| P-M2 | EXL3 amortizes less than GGUF: A_X(4) < A_Q(4) |
| P-M3 | EXL3 amortizes weakly: A_X(4) < 2.0 |
| P-M4 | The ordering holds at 8 rows too: A_X(8) < A_Q(8) |

**Descriptive:** behaviour at ub 16, above both kernels' 8-row limit, where each falls back — EXL3 to
reconstruct plus cuBLAS, GGUF to dequantize plus cuBLAS.

## Declared in advance

- **This is a matmul-cost measurement, not an MTP measurement.** It cannot prove what causes the MTP
  gap. It can only show whether kernel cost scales the way the gap would require.
  - **If P-M2 and P-M3 hold,** the gap has a kernel-level explanation that buun could act on.
  - **If they fail,** the explanation lies elsewhere: draft-head cost, sampling, or scheduling.
- **A(m) understates a perfectly amortizing kernel,** because pp64 includes attention and per-launch
  overheads that do not scale with rows.
- **Load times differ by disk** and are not compared.
- **One prompt length, three reps, one node.**

**Scorer:** `tools/score_exl3_mtp.py`, committed with this prereg.

## Amendment 1 — 2026-09-12 ~18:50, after attempt 1's control failed, before the re-run

**Attempt 1 is kept in `mtp/attempt1_cold/` and is superseded.** Its control (P-M0) failed and the
reason invalidates the headline rather than merely adding noise:

- **EXL3's tg8 read 5.42 t/s at ub 1 and 6.95 t/s at every later ubatch** — a 28.5% spread that is
  entirely the first measurement after the model loads. Q6_K's spread was 0.5%, because it loads in 36 s
  where EXL3 takes 318 s off spinning disk, leaving cold caches and un-ramped clocks for the first test.
- **The same cold start hits `pp64` at ub 1**, which is the baseline every `A(m)` divides by. Attempt 1
  reads A_X(4) = 2.92 against A_Q(4) = 2.94, which would falsify the verification-cost hypothesis — but
  correcting X's baseline by the ~22% the tg8 artifact shows would give A_X(4) ≈ 2.40 against 2.94, which
  would support it. **The run cannot decide between those two readings, so it decides nothing.**

**The change:** the sweep runs `-ub 1,2,4,8,16,1`, so ub 1 is measured twice in the same process — cold
first, warm last.
- **The baseline for every `A(m)` is the warm ub 1 measurement** (the higher of the two).
- **The tg8 control uses the warm value too**, so P-M0 tests node stability rather than re-detecting a
  known cold start.
- **Predictions P-M0 to P-M4 and their thresholds are unchanged.**
