# Prereg -- same-model codec ladder: Bonsai 2 ternary vs GSQ-RCO vs AD, on Qwen3.8-27B

**Written 2026-09-19, before any cell is run.** Predictions committed here first; the result
file scores them mechanically and keeps the wrong ones.

## Why this test exists

`OUTLINE_lowbit_methodology.md` is content notes for a piece answering two public requests in the
`unsloth/Kimi-K3-GGUF` discussion #12. coder543 asked for "benchmarks across various quants" and
said "I find the typical KLD measurements to be an unsatisfying alternative". The outline's
existing ladder (Puzzle-75B, HumanEval+, K=3) answers that on a task metric, but it varies
**quantisation and thinking together**, so it cannot isolate the codec.

This ladder fixes the model and varies only the codec. Every cell is **Qwen3.8-27B**.

## The panel

Scored against the **same reference and corpus as the 26-receipt EXL3 campaign**, so the cells
join one ladder rather than forming a disconnected second one.

| cell | codec | bpw | size | on disk | engine |
|---|---|---:|---:|---|---|
| B-PTQ1 | Bonsai 2 PTQ1_0 (dense trits) | 1.75 | 5.95 GB | **no** | PrismML fork |
| B-PQ2 | Bonsai 2 PQ2_0 (2-bit slots) | 2.13 | 7.21 GB | yes | PrismML fork |
| G-IQ2XS | GSQ-RCO IQ2_XS-mtp | 2.58 | 8.77 GB | yes | buun (stock GGUF) |
| A-IQ2XS | AD IQ2_XS | ? | 9.89 GB | yes | buun |
| G-IQ3XXS | GSQ-RCO IQ3_XXS-mtp | 3.05 | 10.44 GB | yes | buun |
| A-IQ3XXS | AD IQ3_XXS | ? | 12.08 GB | yes | buun |
| A-IQ3S | AD IQ3_S-IQ3_XXS | ? | 12.98 GB | yes | buun |

## Inputs, verified by hash not by name

| input | identity |
|---|---|
| reference model | `Qwen3.8-27B-Q8_0.gguf`, **29,047,086,048 B** -- byte-exact to `PREREG_EXL3_KLD.md` |
| corpus | `wiki.test.raw`, 1.29 MB, sha256 `173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08` -- matches the EXL3 campaign |
| Bonsai PQ2_0 | sha256 `3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1` |

**This verification is not ceremony.** Twelve files named `wiki.test.raw` exist across four
project trees on this machine. All twelve are 14-15 bytes: HTTP `404: Not Found` bodies written
to disk by a fetch that never checked its response. A harness pointed at any of them would have
run to completion and produced numbers. `llama-perplexity` exits 0 on failure
(`exl3-on-pascal` memory), so nothing would have complained.

## Method

Flags frozen from `PREREG_EXL3_KLD.md` so the cells are comparable:
`-ngl 99 -sm layer -c 512 -b 512 -ub 8 --chunks 40 -fa on -ctk f16 -ctv f16`,
`--kl-divergence-base ref.kld --kl-divergence`.

The Q8_0 reference is **a reference, not ground truth**. Every KLD is a distance *from Q8_0*;
only differences between distances to the same reference are meaningful.

Reference regeneration: the 29 GB Q8_0 does not fit 16 GB of VRAM. Either partial offload on the
9070 XT (~13 GB host-side, slow but self-contained) or `.194`'s 4x P100 (64 GB VRAM, native, but
216 s cold boot and 218 W idle). Whichever is used is recorded in the result.

## Predictions

Committed before any cell runs.

| id | prediction | falsified if |
|---|---|---|
| **P-L0** | **Gate.** Re-running the reference against itself gives mean KLD < 1e-4 and same-top >= 99.9%. Without this the ladder is not reproducible and nothing below counts | the self-check fails |
| **P-L1** | KLD decreases monotonically with bpw **within** a codec family (GSQ IQ2_XS > IQ3_XXS; AD IQ2_XS > IQ3_XXS > IQ3_S) | any within-family inversion |
| **P-L2** | **THE FORK.** At the closest size pair -- B-PQ2 (7.21 GB) vs G-IQ2XS (8.77 GB) -- **Bonsai has the lower KLD despite being 1.56 GB smaller and 0.45 bpw lower** | GSQ-RCO's KLD is lower, or they are within 5% |
| **P-L3** | GSQ-RCO beats AD at comparable size, since RCO's per-tensor type assignment under a size budget is exactly the optimisation AD's fixed recipe lacks | AD matches or beats GSQ at the nearer size pair |
| **P-L4** | The ternary cells show a **larger same-top-token drop than their KLD suggests**, because a rotated basis redistributes mass differently than scalar quantisation does. Point estimate: B-PQ2 same-top at least 0.5 pp below a scalar cell of equal KLD | same-top tracks KLD across codec families as tightly as it does within one |

| **P-L5** | **CONTROL PAIR.** B-PTQ1 and B-PQ2 encode the *same* ternary weights in different containers, so their KLD should be **identical to within the reference's own reproducibility floor** (the P-L0 gate, <1e-4). Prediction: `|KLD(B-PTQ1) - KLD(B-PQ2)| < 1e-4` | the two differ by more than the gate, which would mean one packing has an implementation defect rather than a fidelity cost |

**Why P-L5 is worth a 5.95 GB download.** The model card describes both as containers for one
"Ternary g128" representation: weights in {-1, 0, +1}, one shared FP16 scale per group of 128.
PTQ1_0 packs 5 trits per byte (base-3, 3^5 = 243 fits in 256) at 1.75 bpw; PQ2_0 uses 2-bit slots,
4 per byte, at 2.13 bpw. Header inspection agrees: both files carry **851 tensors, 402 quantised +
353 F32 + 96 BF16**, the same `prism.hadamard.*` keys, and `general.architecture = qwen35`.

So this is a **control, not a seventh data point**. It costs one download and it tests the
instrument rather than the codec. If the two agree, every other cell's KLD is trustworthy to that
floor. If they disagree, the ladder has a defect in it and the disagreement is itself the finding.

A corollary worth stating in advance: **if P-L5 holds, PTQ1_0 strictly dominates PQ2_0** --
identical fidelity at 1.26 GB less. PQ2_0's only remaining justification is decode cost
(shift-and-mask versus base-3 unpack), which belongs to the runtime half, not this one.

P-L2 is the question the panel exists to answer: does a rotated ternary basis beat optimised
scalar quantisation at matched-or-better size. P-L4 is the one most likely to be wrong and the
most interesting if it holds, because it would mean KLD alone ranks these codecs incorrectly --
which is precisely coder543's complaint, given evidence.

## Deliberately out of scope for this prereg

Task metrics (HumanEval+, HA-20). The Puzzle ladder took 36.4 h for four cells; seven cells is a
multi-day run. **Sequencing is deliberate:** this distributional pass is cheap (forward passes,
no generation) and its job is to decide which two or three cells deserve the expensive task
metric. Reporting KLD alone as a quality verdict would commit the error the piece criticises.

## What would make this publishable rather than merely done

Both codec families make distributional claims (Bonsai: "98.2% of FP16 intelligence retained";
ISTA: IQ3_S "matches the base model exactly on AIME25"). A same-model, same-corpus,
same-reference ladder spanning 1.75 to 8 bits is a measurement neither vendor published and
almost nobody else is positioned to run.
