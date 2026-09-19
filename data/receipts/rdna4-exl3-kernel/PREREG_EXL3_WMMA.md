# Prereg — independent RDNA4 validation of buun's INT8-WMMA multi-row EXL3 kernel

**Written 2026-09-15 ~18:05, before both builds finished and before any measurement.**

## What's on trial

buun landed two commits on `buun-llama-cpp` master that accelerate multi-row EXL3 matmul on RDNA4 by
decoding the compressed weights straight into INT8 **WMMA** matrix-core fragments instead of per-row
integer dot products:

- `13f4a90d1` — "hip: use RDNA4 INT8 WMMA for multi-row EXL3" (jump 1, ~20.95→32.29 tok/s code, per buun)
- `117300f7e` — "accelerate multi-row EXL3 matrix loads" (jump 2, ~32.5→50.0 code, per buun) — **master tip**

The A/B is **baseline `d654c90d9` (parent of jump 1) vs tip `117300f7e`** — the full cumulative change in
one comparison, which also tests buun's "numerics preserved through both commits" claim end-to-end. Both
built HIP/gfx1201, `-DGGML_HIP_NO_VMM=OFF`, Release, identical flags; the *only* variable is the two commits.

Target: `GestaltLabs/Qwen3.8-27B-EXL3-11.5GB` (has embedded `mtp.*` heads → MTP is self-speculative, no
sidecar). Hardware: RX 9070 XT (gfx1201) — **a different RDNA4 card than buun's**, so absolute tok/s will
differ; every prediction is scored as a **tip/base ratio on this card**, never against buun's absolute numbers.

## Why MTP is required to see it

The new path fires only on the **3/4/8-row** cases (buun's own words) — exactly MTP verification batch sizes
(a 2–7-token draft + 1). One-token decode stays on the old kernel; large prefill batches take yet another
path. So MTP-on is the condition that exercises the kernel; no-MTP decode is the control that must *not* move.

## Predictions (committed before data)

| id | prediction | falsified if |
|---|---|---|
| **P1 — numerics preserved** | at temp 0 on fixed code+prose prompts, the top-k **logprob values are bit-identical** base↔tip (and the greedy token sequences match) | any logprob differs beyond fp round-trip, or token sequences diverge |
| **P2 — control, no-MTP decode unchanged** | single-stream decode (MTP off) is within the ±3% noise floor base↔tip | plain decode moves >3% — the kernel touched the 1-row path it shouldn't |
| **P3 — MTP decode faster on tip** | with MTP on, **tip/base decode ratio > 1.15** on both code and prose; direction and rough magnitude consistent with buun (~1.5× code / ~1.6× prose) | ratio ≤ noise, or tip slower |
| **P4 — acceptance unchanged** | MTP draft acceptance is within ±0.03 base↔tip (kernel changes speed, not draft quality) | acceptance moves >0.03 — the kernel altered outputs, contradicting P1 |
| **P5 — prefill ~unchanged** | large-batch prefill tok/s is within ~5% base↔tip (kernel targets the 3–8-row regime, not hundred-row prefill) | prefill also speeds up materially — then the kernel helps more paths than buun claimed (a *bonus* finding, still logged) |

**The two that can't fake success are P1 and P4** — if the kernel changed what the model computes, no speedup
matters. P3 is the headline buun cares about; P2/P5 are the controls that keep P3 honest (a speedup that also
moved the 1-row or prefill path would mean the variable wasn't isolated).

## Method

For each build (base, then tip), one `llama-server` per config, page-relevant state fixed:
1. **MTP on** (`--spec-type draft-mtp`, embedded head), temp 0, `--ctx-checkpoints 0`, fixed seed: run one code
   prompt and one prose prompt to a fixed output budget. Capture prefill tok/s, decode tok/s, MTP acceptance
   (from server timings), the output token sequence, and top-k logprobs (`n_probs`).
2. **MTP off** (same prompts, same temp 0): decode tok/s — the P2 control.
Compare tip vs base as ratios; P1/P4 compared as equality within tolerance. 3 reps per number, rep-0 discarded,
median — same noise discipline as the spill campaign (a spill-campaign-measured ~3% decode floor applies).

**Open harness detail, resolved empirically on the tip binary (not a free parameter):** the exact flag form for
MTP on an EXL3 dir with an *embedded* head (docs show GGUF + `-md` sidecar; EXL3-embedded is undocumented). The
server log must confirm MTP engaged (draft slots > 0) or the arm doesn't count — a readiness probe that can't
succeed unless MTP actually ran.

## Not claimed

buun's absolute tok/s (different card). Whether jump 1 vs jump 2 each contributed — this A/B tests the sum; if
P1 fails, *then* bisect by building the middle commit `13f4a90d1` to find which commit broke numerics.
