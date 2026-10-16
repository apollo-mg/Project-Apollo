# Pre-registration -- did NVIDIA's compression or its 2-bit training break Bolt's calibration?

**Registered 2026-10-15, before any row of either new arm.** Downloads were running; no file was complete or loaded.

**Why.** On M1, Super VL 120B-A12B (NVFP4) refuses 0.92 of invented items (`RESULT_SUPERVL.md`) and its derivative Bolt
74B-A9B (NVIDIA's 2-bit QAT file) refuses 0.16 (`RESULT_BOLT.md`). NVIDIA's cards state Bolt was made in two steps:
(1) compression from Super VL with Star Elastic (router-guided architecture search and pruning; a BF16 release of the
compressed model exists), then (2) 2-bit quantization-aware training (IQ2). Mark's question: which step did it?

**Prior art checked:** `ledger_precheck.py "quant-abstention UNKNOWN abstention"` and the coder-prune receipt:
- `RESULT_MAIN.md`: on the 27B, UD-Q2_K_XL keeps refusal (0.61 vs 0.60 at Q8_0) while losing knowledge;
- `RESULT_FLASHNEXT.md`: Flash-Next Q2 refuses 0.71, same as its IQ4;
- `coder-prune/RESULT_CODER_PRUNE.md`: KL-optimised expert pruning took fabrication from 14 % to 52 % with zero
  refusals.

**What this adds:** a direct split of compression from quantization on one model family.

## Arms (instrument as `PREREG_BOLT.md`: M1, thinking off, greedy, 1024 tokens, CAL grading, `run_main.py`)

| arm | file | role | host / placement |
|---|---|---|---|
| **BOLTQ8** | AtomicChat `AD-Q8_0` (2 shards, 78,852,778,848 B), built from NVIDIA's Bolt BF16 with AtomicChat's imatrix; their measured KL to BF16 0.0084 | Bolt without the 2-bit step (compressed model at near-full precision); bytes match FNQ2 (78.87 GB) and SVNV (76.9 GB) | .194, 4 P100, v0.7.0, flags as SVNV; expert spill and `-ts` found the same way (smallest K that loads), recorded as placement |
| **BOLTPQ2** | AtomicChat `AD-IQ1_M_S` (21,939,907,488 B), post-training 2-bit from the same BF16; their KL 0.194 | plain 2-bit quantization at NVIDIA's file size (22.02 GB, 0.4 % apart) | .73, 2 P100, v0.7.0, flags as BOLT (fully resident) |

Stored references: `BOLT` (NVIDIA 2-bit QAT), `SVNV` (Super VL NVFP4), `C.A` (27B Q8_0). Files verified against the
HF lfs sha256 before loading. `--expect-variants` not passed; UNKNOWN ids recorded (they were single tokens for BOLT
and SVNV).

## Readings and predictions (`analyze_bolt_split.py`, committed with this file; paired bootstrap, 10,000, seed 20261017)

| # | question | rule | my bet | confidence |
|---|---|---|---|---|
| P1 | **Compression costs calibration even without the 2-bit step** | U refusal BOLTQ8 - SVNV <= -0.20, CI upper < 0 | holds | 0.65 |
| P2 | **Compression explains more of the loss than the 2-bit step** | (SVNV - BOLTQ8) > (BOLTQ8 - BOLT) on U refusal, point estimates | holds | 0.65 |
| P3 | **Compression costs knowledge** | H acc BOLTQ8 - SVNV <= -0.15, CI upper < 0 | holds | 0.7 |
| P4 | **Plain 2-bit is at least as calibrated as NVIDIA's QAT 2-bit at the same size** | U refusal BOLTPQ2 - BOLT >= 0, CI lower > -0.07 | holds | 0.5 |
| P5 | **Thinking off keeps answers short** | TRUNCATED <= 2 % in each new arm | holds | 0.85 |

Reported without prediction: H acc BOLTPQ2 - BOLT (does QAT buy knowledge at 2 bits?), BOLTQ8 - BOLT on H acc, all
rates, slot P(UNKNOWN) per arm.

**Interpretation fixed in advance.** P1 holding and BOLTQ8 near BOLT = the compression broke it. BOLTQ8 near SVNV
(refusal within 0.10) = the 2-bit step broke it; P4 then says whether QAT specifically or 2 bits in general. Both
gaps large = both steps cost.

## Stop rules

As `PREREG_BOLT.md`. Additionally: a file that fails its sha256 is re-downloaded, never loaded.
