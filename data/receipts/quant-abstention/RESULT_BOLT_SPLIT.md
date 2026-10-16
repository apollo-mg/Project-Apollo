# Result -- Bolt's calibration was lost in three steps: compression 0.92 -> 0.65, plain 2-bit -> 0.44, NVIDIA's quantization-aware distillation -> 0.16

**Prereg:** `PREREG_BOLT_SPLIT.md` (`ddeb6fb1`, before either new row). **Analysis:** `analyze_bolt_split.py` ->
`RESULT_bolt_split.json`. **Raw:** `raw/main_BOLTQ8.jsonl`, `raw/main_BOLTPQ2.jsonl` (240 rows each); references
`main_SVNV`, `main_BOLT`, `main_C.A`.

**Runs (2026-10-15/16):**
- **BOLTQ8**: AtomicChat `AD-Q8_0` (built from NVIDIA's Bolt BF16; their KL to BF16 0.0084), 78.85 GB, sha256 verified.
  .194, 4x P100 150 W / 1063 MHz, v0.7.0, SVNV's flags; placement by the registered procedure: smallest spill that
  loads was the last **8** MoE layers' experts on CPU with `-ts 18,19,15,37` (CUDA model buffers 10.3 / 15.4 / 15.5 /
  15.5 GB; ~250-450 MB free per GPU; no OOM in the run). `/props` confirmed the file. Decode ~15 tok/s.
- **BOLTPQ2**: AtomicChat `AD-IQ1_M_S` (post-training 2-bit from the same BF16; their KL 0.194), 21.94 GB, sha256
  verified. .73, 2x P100 150 W / 1328 MHz, v0.7.0, BOLT's flags, fully resident. `/props` confirmed the file.
- Both: 240/240 `finish: stop`, `reasoning` empty on every row, one `Exact Answer:` per row, lenient grader changes no
  grade, no prose refusals among wrong invented-item answers. No deviations.

## The chain

| step | arm | bytes | easy | hard | invented: refused | slot P(UNKNOWN), invented |
|---|---|---:|---:|---:|---:|---:|
| parent | **SVNV** Super VL NVFP4 | 76.9 GB | 0.95 | **0.86** | **0.92** | 0.930 |
| after compression (+ Bolt's post-training) | **BOLTQ8** Bolt AD-Q8_0 | 78.9 GB | 0.775 | **0.51** | **0.65** | 0.525 |
| + plain 2-bit | **BOLTPQ2** Bolt AD-IQ1_M_S | 21.9 GB | 0.625 | **0.34** | **0.44** | 0.659 |
| NVIDIA's 2-bit (QAD) instead | **BOLT** NVIDIA 24GB GGUF | 22.0 GB | 0.675 | **0.41** | **0.16** | 0.344 |
| reference | 27B Q8_0 | | 0.85 | 0.50 | 0.60 | 0.699 |

## Registered verdicts

| # | prediction | outcome |
|---|---|---|
| P1 | compression costs calibration even without the 2-bit step | **holds**: refusal BOLTQ8 - SVNV -0.27 [-0.37, -0.18] |
| P2 | compression explains more of the refusal loss than the 2-bit step | **does not hold**: compression 0.27, 2-bit step 0.49 |
| P3 | compression costs knowledge | **holds**: hard BOLTQ8 - SVNV -0.35 [-0.45, -0.25] |
| P4 | plain 2-bit at least as calibrated as NVIDIA's QAT at the same size | **holds**: +0.28 [+0.19, +0.37] |
| P5 | <= 2 % truncated, each new arm | **holds**: 0 % and 0 % |

Reported: BOLTQ8 - BOLT hard +0.10 [+0.04, +0.17], refusal +0.49 [+0.39, +0.59]; BOLTPQ2 - BOLT hard -0.07
[-0.15, +0.01].

## Reading

Mark asked whether NVIDIA broke Bolt with the pruning or the quantization. **Both, in different currencies.**

- **Knowledge was lost mainly in compression**: hard 0.86 -> 0.51 (-0.35). Going to 2 bits cost a further 0.17
  plainly; NVIDIA's distillation won back 0.07 of that.
- **Calibration was lost mainly in the 2-bit step, and most of that is NVIDIA's distillation**: refusal 0.92 -> 0.65
  in compression (-0.27), 0.65 -> 0.44 for plain 2 bits (-0.21), and 0.44 -> 0.16 for the QAD file at the same size
  instead (-0.28). The QAD file trades refusals for a little knowledge: against plain 2-bit it answers 7 points more
  hard items right and refuses 28 points fewer invented ones, and its forced slot flattens (0.66 -> 0.34).
- My bet that compression was the main culprit was right for knowledge and wrong for calibration.
- Compressed Bolt at near-full precision lands on the 27B dense at 8 bits (hard 0.51 vs 0.50, refusal 0.65 vs 0.60).

NVIDIA's card describes every post-compression stage as targeting agentic tasks and task completion (SFT for AIME, GPQA,
Terminal Bench; E2E GRPO for MCP and SWE; a GenRM with a reasoning-length penalty; QAD with on-policy Terminal rollouts
to prevent regressions). Nothing in that recipe rewards "I don't know", and the step that changed the weights most at
2 bits, QAD, cost the most calibration.

## Not established

- **"Compression" here is compression plus Bolt's later post-training.** The BF16 release, and so BOLTQ8, comes after
  Bolt's vision, SFT and RL stages; the pure pruning effect cannot be separated with public files.
- **The parent is measured at NVFP4 (~4-bit), Bolt at 8 bits.** If anything this understates the compression cost.
- AtomicChat's imatrix quants, not NVIDIA's; KL to BF16 reported by AtomicChat, not re-measured here.
- Thinking off only (a thinking-on probe on BOLT is running separately, `EXPLORE_THINK_BOLT.md`). One instrument,
  240 items.
