# Result — EXL3 works as a drop-in for the daily driver, at 0.65× its speed: MTP buys EXL3 1.24×, GGUF 1.69×

**Run 2026-09-12, 15:21–15:50, on `.73`'s two P100s.** Pre-registered in `PREREG_EXL3_DROPIN.md`
(`7277557`) and scored by `tools/score_exl3_dropin.py`, which was committed with the prereg. Scorer
output is in `dropin/score_output.txt`; raw data in `dropin/` (`c9e83d4`). EXL3 campaign test 1: ledger
entries O2, O3, O4 and O5, plus a first O7 number.

## Headline

EXL3 was swapped into the daily driver's exact command: MTP drafting, the F16 mmproj, VBR KV at 262,144,
and `-sm tensor`. It **loads, drafts, reads images, and prefills as fast as the GGUF**. At the served
sampling it **decodes at 0.646× the daily driver**: 13.08 t/s against 20.25.

| arm | binary | weights | MTP | greedy t/s | acceptance | sampled t/s | prefill t/s (14,852 tok) | VRAM MiB (GPU0 + GPU1) | load |
|---|---|---|---|---|---|---|---|---|---|
| **X** | QUAL | EXL3 4.00bpw | on | **13.96** | 0.693 | **13.08** | 153.7 | 9,433 + 8,297 | 322 s (HDD) |
| Xn | QUAL | EXL3 4.00bpw | off | 11.22 | – | 10.94 | 157.5 | 8,227 + 7,091 | 202 s (HDD, warm cache) |
| **Q** | QUAL | Q6_K | on | **22.27** | 0.688 | 20.71 | 150.1 | 13,461 + 12,325 | 36 s (NVMe) |
| Qn | QUAL | Q6_K | off | 13.18 | – | 13.17 | 153.4 | 12,199 + 11,063 | 36 s |
| **D** | DEPLOYED | Q6_K | on | 22.38 | 0.692 | **20.25** | 151.2 | 13,461 + 12,325 | 31 s |

- **QUAL** is buun `9ae8f0f40` plus the e8m0 guard. **DEPLOYED** is `c9c52d71`, which the wake proxy
  launches.
- **Every arm answered "Paris" and read KESTREL off the vision probe.**
- **Decode figures** are medians of 3 × 256 tokens. Acceptance is Σ accepted / Σ drafted over those reps.

## The MTP asymmetry — the main finding

| | with MTP | without | gain | greedy acceptance |
|---|---|---|---|---|
| Q6_K | 22.27 | 13.18 | **1.69×** | 455 / 661 = 0.688 |
| EXL3 | 13.96 | 11.22 | **1.24×** | 451 / 651 = 0.693 |

**Both formats accept the same drafts at the same rate, but EXL3 gets a third less speedup from them.** So
the lost speedup is in *verification*, not drafting. EXL3's 4-bit MTP head (`mtp_bits 4`) drafts as well
as the GGUF head does.

**Hypothesis, not tested:**
- **The shared step.** Each accepted-draft step verifies a batch of up to 4 rows.
- **GGUF amortizes it.** It runs that batch on MMVQ (`ggml-cuda.cu:2688`, rows ≤ `MMVQ_MAX_BATCH_SIZE`),
  which reads each weight once for all rows. On a bandwidth-bound P100, a 4-row verify costs about what
  one row costs.
- **EXL3 may not.** It runs the same batch on its int8 path (`exl3.cu:280`, m ≤ `MAX_M`). If that path
  pays the trellis decode per row, or otherwise scales with rows, verification eats the speedup.

**The test that separates the two** is a `--draft-max` sweep (1, 3, 7) on both weights, or timing the EXL3
int8 GEMV directly at m = 1 to 8. If the hypothesis holds, the fix is upstream, in buun's kernel.

**Consequence:** EXL3 *with* MTP (13.96 t/s) barely beats Q6_K *without* it (13.18, +6%).

## Predictions

| id | prediction | result |
|---|---|---|
| P-D1 | X loads with the full daily-driver flag set | **CONFIRMED** |
| P-D2 | MTP engages on X in every rep | **CONFIRMED.** 6 of 6 reps drafted and accepted |
| P-D3 | X's greedy acceptance is within 10 points of Q's | **CONFIRMED.** 0.693 vs 0.688 |
| P-D4 | X's greedy decode is ≥ 0.80× Q's | **FALSIFIED.** 0.627× |
| P-D5 | X with MTP beats Qn without it | **CONFIRMED, narrowly.** 13.96 vs 13.18 |
| P-D6 | X reads the probe | **CONFIRMED.** "KESTREL" |
| P-D7 | VBR is live on X: `kv_bpv` below 16 at load | **FALSIFIED as written.** The criterion was uninformative (see below) |
| P-D8 | D and Q decode within 5% of each other | **CONFIRMED.** 1.005×, so the binary change is not a confound |
| P-D9 | X's prefill is ≥ 0.70× Q's | **CONFIRMED.** 1.02×: 153.7 vs 150.1 t/s |
| P-D10 | MTP gains ≥ 1.5× on EXL3 | **FALSIFIED.** 1.24× |

**7 confirmed, 3 falsified.**

## Measured but not predicted

- **What P-D7 actually measured.**
  - Both X and Q log the identical controller line: *"VBR dynamic turbo runtime controller: KV budget
    auto (remaining VRAM, resolved by fit), entry tier f16, floor 2.25 bits/value"*.
  - **Every arm read `kv_bpv` 16.0 at load and still read 16.0 after the 14,852-token prefill.** No arm
    ever left VBR's f16 entry tier.
  - So the criterion tested whether VBR's entry tier is f16, which it is on both formats. It could not
    tell VBR-on from VBR-off, and our own receipts already recorded 16.0 as VBR's normal reading when it
    has headroom.
  - **What this test does show:** VBR composes with EXL3 weights at load. **What it does not:** VBR's
    degraded tiers were never exercised with EXL3 weights. The deployed binary logs no controller line
    at all; it is an older build, and nothing is claimed about it.
- **EXL3 frees about 8 GB of VRAM at the daily driver's config:** 17.7 vs 25.8 GB across both cards,
  with the mmproj on GPU0 in both.
- **Prefill is at parity** at about 15k tokens, 153.7 vs 150.1 t/s. On sm_60 both formats rebuild
  weights to fp16 and run cuBLAS for batched matmuls, so parity is plausible.
- **Loading is the deployment problem.** X took 322 s off `/mnt/HDD`, Q took 36 s off NVMe. `.73`
  reloads its model on every wake, so as deployed today, EXL3 would turn the 77–99 s cold start into
  about 6 minutes. On NVMe it should load faster than the Q6_K (16.88 vs 22.88 GB), but that is
  untested: `/mnt/models` has 9.9 GB free.

## For the ledger (`CAMPAIGN_EXL3.md`)

- **O2 (MTP): RETIRED, with a cost.** MTP engages at GGUF's acceptance rate but buys 1.24× instead of
  1.69×. That cost is carried in O5.
- **O3 (vision): RETIRED.** The daily driver's existing `mmproj-F16.gguf` attaches and reads the probe.
- **O4 (VBR): RETIRED at load.** The degrade path stays OPEN.
- **O5 (slower): CONFIRMED.**
  - 0.646× the daily driver as served.
  - 0.627× matched, with MTP on.
  - 0.85× matched, with MTP off (inference receipt).
  - The charter's ~0.45× estimate is superseded.
- **O7 (prefill):** parity at about 15k tokens. Long context is still untested.
- **O10 (load time): CONFIRMED as deployed** (spinning disk). OPEN on NVMe, which is blocked on disk
  space.

## Deviations and limits

- **One prompt, 256 tokens, 3 reps per arm.** These are speed estimates, not distributions. One image
  probe, one prefill length.
- **Sampled acceptance differs between Q and D** (0.640 vs 0.598), with the same seeds on two binaries.
  No prediction depends on it, and the greedy acceptances agree (0.688 vs 0.692).
- **Xn's load (202 s) ran on a partly warm page cache** after X's load. Load times are not compared
  across arms except as the deployment note above.
- **The orchestrator's launch ssh held about 60 s** before logging (the driver started at 15:21:48; the
  launch was logged at 15:22:51). This was cosmetic; no stage was affected.
- **The dev-diary ledger was not affected by this test.** The proxy was paused 15:21:46–15:50:30,
  between its 15:05 and 16:05 runs.
