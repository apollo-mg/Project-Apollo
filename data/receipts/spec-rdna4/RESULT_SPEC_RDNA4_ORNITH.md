# RDNA4 speculative decoding: depth and content both decide the winner

**2026-08-26.** 9070 XT (gfx1201), `Ornith-1.5-9B-AD-Q8_0-Q6_K` (32 blocks, 8 full-attn KV
layers at 3–31, `qwen35` arch). MTP head from `Ornith-1.5-9B-MTP-Q6_K` (33 blocks — `blk.32`
is the head). DFlash draft: `ornith1.5-9b-dflash-bf16-projection-Q4_K_M` (0.71 GB).
`-ngl 99 -c 8192 -np 1 --jinja`, temp 0, 400 max tokens. Two prompt types.

**Binary: TheTom/llama-cpp-turboquant `f97400563`** (`feature/turboquant-kv-cache`, built
2026-08-26 for gfx1201). Built in a **worktree** — the existing checkout was 935 behind AND
338 ahead after an upstream rebase, so it was left untouched.

## Results, tok/s

| arm | prose | code | acc prose | acc code |
|---|---:|---:|---:|---:|
| baseline (no spec) | 61.94 | 62.10 | — | — |
| MTP n=2 | **85.72** | 92.06 | 0.534 | 0.612 |
| MTP n=8 | 55.50 | 69.94 | 0.182 | 0.260 |
| MTP n=15 | 39.48 | 46.89 | 0.098 | 0.142 |
| MTP adaptive | 79.40 | 100.31 | 0.411 | 0.611 |
| DFlash n=2 | 78.10 | 98.14 | 0.500 | 0.734 |
| **DFlash n=8** | 75.30 | **110.08** | 0.198 | 0.336 |
| DFlash n=15 | 64.20 | 93.36 | 0.096 | 0.182 |

## [1] There is no single best setting — it depends on depth AND content

- **Best overall: DFlash n=8 on code, 110.08 tok/s = 1.77x baseline.**
- **Best on prose: MTP n=2, 85.72 = 1.38x.** DFlash never wins prose at any depth.
- Every arm beats baseline on code; on prose, MTP n=8/n=15 are **slower than not speculating**.

Recommending one `--spec-draft-n-max` for this hardware would be wrong for half the workload.

## [2] MTP collapses with depth; DFlash degrades gracefully

MTP acceptance falls 0.534 → 0.182 → 0.098 (prose) as n goes 2 → 8 → 15, and throughput with
it. DFlash falls too (0.500 → 0.198 → 0.096) but keeps winning to n=8 because its draft is
cheap enough that rejected tokens cost less.

**This refines the 08-18 receipt.** That found DFlash climbing *monotonically to n=15* on
RDNA4 (peak 150.66). Here DFlash peaks at **n=8** and falls back by n=15. Different model
(9B vs 27B) and a much newer build, so this does not contradict it — the depth optimum is
model-dependent, and "monotonic to 15" should not be carried forward as a hardware constant.

## [3] The content split reproduces

`INDEX.md` (08-15): *DFlash wins code/SQL/JSON, MTP wins prose*. Reproduced here on a
different model and a fresh build — DFlash 110.08 vs MTP 69.94 on code at n=8, while MTP n=2
leads on prose. Acceptance is uniformly higher on code for both drafters, which is the
mechanism: code is more predictable, so drafts survive.

## [4] `draft-mtp-adaptive` is real but not sufficient

Tom's fork has `draft-mtp-adaptive`; buun's does not. It reaches 100.31 on code — better than
any fixed-n MTP — and 79.40 on prose, below fixed n=2. So adaptive depth recovers much of
MTP's depth loss without closing the gap to a good drafter (DFlash n=8, 110.08).

## Fork divergence, as of today

| feature | TheTom `f97400563` | buun `2714303` |
|---|---|---|
| `draft-mtp-adaptive` | **yes** | no |
| DFlash2 | no | **yes** (`llama-cparams.h`, `llama-model.cpp`) |
| `draft-dspark` | yes | yes |

Cross-fork sanity: baseline 61.94 vs 63.40 and MTP n=2 85.72/92.06 vs 86.85/96.05 — the two
builds agree on the arms that worked, which is what makes the DFlash failure below a real bug
rather than a build difference.
