# Result - independent RDNA4 validation of buun's INT8-WMMA multi-row EXL3 kernel

**Run + scored 2026-09-15 18:49 on the RX 9070 XT (gfx1201).** Prereg: `PREREG_EXL3_WMMA.md` (written
before any measurement). Data: `ab_results.jsonl`. Harness: `run_ab.py`.

## Setup

base `d654c90d9` vs tip `117300f7e` (both WMMA jumps), built identically HIP/gfx1201
`-DGGML_HIP_NO_VMM=OFF` Release - the two commits are the only variable. Target
`GestaltLabs/Qwen3.8-27B-EXL3-11.5GB` with its **embedded MTP head** (`--spec-type draft-mtp
--spec-mtp-vocab-size 32768`, no sidecar). KV pinned `f16` on both sides (buun's default is VBR;
overridden so KV is identical and can't drift). temp 0, 128-token generations, 3 reps, rep 0 discarded,
median of reps 1-2. A different RDNA4 card than buun's, so every number is scored as a **tip/base ratio**.

## Scorecard

| id | prediction | result | verdict |
|---|---|---|---|
| **P1 numerics** | top-20 logprobs bit-identical base vs tip | **identical** (full top-20 array equal; top token " Paris" @ -0.31830495595932007 on both) | **CONFIRMED** |
| **P2 control (no-MTP decode)** | plain decode unchanged (<3%) | code 23.3->23.4 (1.004), prose 23.5->23.5 (0.999) | **CONFIRMED** |
| **P3 headline (MTP decode)** | tip/base > 1.15 | **code 21.9->44.4 = 2.03x**, **prose 19.8->42.8 = 2.16x** | **CONFIRMED** |
| **P4 acceptance** | within 0.03 base vs tip | code 0.811 vs 0.811 (delta 0.000), prose 0.695 vs 0.695 (delta 0.000) | **CONFIRMED** |
| **P5 prefill** | within 5% | **inconclusive** - prefill over a 25-token prompt is noise-dominated (tip/prose reps 26.4/51.6); can't resolve at this length | **UNRESOLVED** |

## What it means

**buun's kernel does exactly what he says, independently on our card.** The tip roughly **doubles MTP
decode throughput** (2.03x code / 2.16x prose - consistent with his cumulative ~20.95->50 code ~2.4x on
his RDNA4 card, ours ~2.0x on the 9070 XT), and it does so **losslessly**: the top-20 logprobs are
bit-identical and MTP acceptance is bit-identical to the last digit. The two checks that can't fake
success - P1 (numerics) and P4 (acceptance) - both passed perfectly. The single-token path (P2) is
untouched, so the variable was isolated: the speedup is pure multi-row verification efficiency.

**This is the clean empirical version of the point in the Brian/HF correction.** Speedup went 2x at
**constant acceptance** and **identical outputs**. That directly falsifies "speedup is entirely a function
of acceptance rate" (acceptance didn't move at all; the kernel did) and confirms distribution-preservation
(bit-identical logprobs -> the kernel changes speed, not content). The reply's two corrections are now
backed by a measurement, not just theory.

**P5 stays open honestly.** The MTP-mode prefill looked like a consistent +15% on tip, but the cleaner
plain-mode prefill control was too noisy at a 25-token prompt (tip/prose 26.4-51.6) to trust it. Whether the
WMMA path also accelerates large-batch prompt processing needs a dedicated long-prompt (500+ token) test.
Not claimed here.

## Notes

- Prose acceptance (0.695) is a **temp-0** figure, higher than a real creative-temperature run would show;
  it is identical base vs tip, which is the only thing P4 rests on. The tip/base *ratio* was on trial, never
  the absolute acceptance.
- Jump attribution not tested: this A/B is baseline vs both commits summed. Since P1 passed (numerics
  preserved end-to-end), no bisect of `13f4a90d1` was needed.
