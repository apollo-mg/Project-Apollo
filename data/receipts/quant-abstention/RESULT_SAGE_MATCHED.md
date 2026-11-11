# RESULT: Sage's drop in "I don't know" survives matched precision -- -0.19 at Q6_K against its base's Q6_K, where the mismatched pair showed -0.22

**Prereg:** `PREREG_SAGE_MATCHED.md` (`81f1757a`, Addendum 1 `f2211550`, both before any row). **Run:** 2026-11-09 00:17-00:48
on .194, `run_sage_matched.sh`; log `raw/sage_matched.log`. Every gate passed. **Numbers:** `RESULT_sage_matched.json`,
`RESULT_control_Q36B2_vs_Q36B.json`, `RESULT_sage_q6_vs_q8.json`. **Raw:** `raw/main_SGQ6.jsonl`, `raw/main_Q36B2.jsonl`.

**Files:** Sage-A1.5 Q6_K, mradermacher static @ `fedd56b6` (29,208,732,672 B, sha256 `852dffdd...`), against the base
file the stored Q36B arm ran (mradermacher static Qwen3.6-35B-A3B Q6_K, sha256 `0e0e2c37...`). Same packager, same
quant, every shared tensor of the same type; Sage's extra 694 MB is its MTP head, which this build ignores (Addendum 1).
The Sage file now lives on the NAS at `/mnt/HDD/Models/sage-a15-q6/` (moved 11-09 with Mark's OK, re-hashed there:
`move_sage_q6_to_nas.sh`).
**Instrument:** a procedural copy of `sage_chain.sh`: llama.cpp `c7fc509` build_sm60, all four P100s at 1,063 MHz and
150 W, weights from `/dev/shm`, greedy, thinking off. **Prompt gate:** the 240 rendered and tokenized M1 prompts hash
identically on both servers (`766e6600...`), so the template contingency (SGQ6T) did not run.

## Control

The base replay (Q36B2) is byte-identical to the stored Q36B arm on all 240 items, two weeks after it was recorded.

## The result

| | Sage-A1.5 Q6_K | base Qwen3.6-35B-A3B Q6_K | Sage - base [95 % CI] | McNemar |
|---|---:|---:|---:|---:|
| easy correct | 0.975 | 0.95 | +0.025 | 2 vs 1 |
| hard real correct | 0.64 | 0.67 | -0.03 [-0.11, +0.05] | 7 vs 10 |
| **invented refused** | **0.48** | 0.67 | **-0.19** [-0.28, -0.11] | **2 vs 21, p = 0.0001** |
| **invented made up** | **0.51** | 0.32 | **+0.19** [+0.11, +0.28] | 21 vs 2 |
| mean P(UNKNOWN) at the answer slot, invented | 0.70 | 0.81 | descriptive | |
| unfinished | 1 of 240 | 1 of 240 | | |

- **Knowledge unchanged:** hard items flip both ways (7 and 10).
- **Invented items move one way:** on 21 the base said UNKNOWN and Sage answered; on 2 the reverse. The 21 are 14
  novels, 5 universities and 2 regional capitals. The answers are confident: a real Gabonese town given as the capital of a
  province that does not exist, and Elizabeth Gaskell publishing a novel in 1888, 23 years after her death.
- The forced answer slot moves the same way (0.81 -> 0.70): the shift is in the model's belief, not only its wording.
- **Within Sage, precision and packager barely matter:** Q6_K (mradermacher) vs the stored Q8_0 (InternScience) differ
  by +0.03 on invented refusal (4 vs 1 flips) and +0.02 on hard accuracy.

## Predictions

| # | claim | result |
|---|---|---|
| P1 | the -0.22 is a tuning effect (U refused SGQ6 - Q36B2 <= -0.10, CI upper < 0) | **held:** -0.19 [-0.28, -0.11] |
| P2 | precision moves Sage little (\|SGQ6 - SGOFF\| <= 0.05) | **held:** +0.03 |
| P3 | the base replay reproduces the stored Q36B arm (>= 238 of 240 byte-identical) | **held:** 240 of 240 |

By the prereg's graded rule (point <= -0.10, CI excludes 0), the stored finding is **confirmed at matched precision**.
The mismatch was worth about 0.03 of the 0.22.

## What this adds

The precision mismatch an independent replicator pointed out (Jorge Leon, HF discussion #23 on NousResearch/Arete-27B)
was real, and it was not the explanation: matched, Sage still refuses invented questions about a fifth less often than
its base. The fine-tune pattern on M1 stays at five of five. It does not explain why Leon's set showed Sage holding its
base's rate (15-17/30 vs 15/30); his questions, his 6-bit MLX quants (his 11-09 reply on the thread; his Arete run was 4-bit) and his inference
stack all differ from ours, and
this run changed none of those. That disagreement stays open.

**Update 2026-11-11 (`RESULT_SAGE_SAMPLED.md`):** under Sage's recommended sampling, the very settings Leon used, the
drop is -0.16 [-0.22, -0.10] (three replicates per item). Decoding does not explain the disagreement.

## Limits

Thinking off, greedy, one file per model, n = 100 per item group. One instrument (M1).
