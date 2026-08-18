No objection to the ignore entry. @jasstrong's four-arch run is stronger evidence for it than mine, for two reasons I want to state plainly before adding anything.

First, their comparison axis is better for this question. They ran D-gate `a70a324f` → LUT-gate `f050a2501`, which isolates the gate. I ran `fca3093c9` → `f6124e914`, which bundles everything between the pre-fix baseline and the merge. For "did the gate cost anything", theirs is the cleaner instrument.

Second, their noise floor is better. Their f16 controls move 0.0–0.5%; mine moved 1.1–1.2% and two of my D=256 cells came back at ~6%. Where we agree, weight theirs.

Two things I can add that their run wouldn't have surfaced.

## Direct dispatch evidence for the ncols question, at D=128

You wrote that `ncols=2` is a shape decode really launches, and that this is what makes a residual there matter. jasstrong's D=256 run establishes `ncols=1` as the launched shape there. I can check D=128 — where the shapes in question actually live — from the dispatch side.

No `rocprof` on this box, but `AMD_LOG_LEVEL=4` prints every dispatch's `ShaderName` with template arguments intact. Build `f6124e914`, `-fa 1`, `TURBO_AUTO_ASYMMETRIC=0`, types per the fork's `ggml.h` (`8=Q8_0 43=TURBO2 44=TURBO3 47=TURBO4`):

| config | kernel launched | count |
|---|---|---:|
| D=128, GQA 3:1, decode | `flash_attn_ext_vec<128, 1, TURBO3, Q8_0>` | 84 |
| D=256, GQA 4:1, decode | `flash_attn_ext_vec<256, 1, TURBO3, Q8_0>` | 40 |
| D=256, GQA 6:1, decode | `flash_attn_ext_vec<256, 1, TURBO3, Q8_0>` | 80 |
| D=128, decode at depth 4096 | `flash_attn_ext_vec<128, 1, TURBO3, Q8_0>` | 112 |
| D=128, turbo3 symmetric | `flash_attn_ext_vec<128, 1, TURBO3, TURBO3>` | 84 |

Every one is `ncols=1`. Three GQA ratios, two head dims, and the packing factor never moves the VEC `ncols`. Depth changes the launch count (84 → 112) and not the shape, which is the control behaving.

So `ncols=1` is the launched shape at D=128 as well as D=256 — jasstrong's result from the gate side, mine from the dispatch side, covering both head sizes. On gfx1201, ordinary decode never reaches `<128,2,…>`.

That supports the ignore entry rather than complicating it: the shapes being exempted are less live than the premise assumed. What I can't tell you is what *does* launch `ncols=2` — speculation and multi-sequence batching are the obvious candidates and `llama-bench` produces neither. Happy to run the census on any config you name.

## `llama-bench` can't prefill with quantized KV on gfx1201

Found while trying to add a prefill regime so the runtime evidence wasn't decode-only. Same build, `llama-bench` vs `llama-server`:

| path | config | result |
|---|---|---|
| `llama-bench` | `-p 256 -n 0`, any quantized KV | ROCm error → abort, `ggml-cuda.cu:109` |
| `llama-server` | ~2000-token prompt, `turbo3`/`q8_0` | fine, coherent output |

The threshold is exact and sits on your HIP VEC/TILE boundary in `ggml_cuda_get_best_fattn_kernel`:

| | |
|---|---|
| `-p 8` | ok |
| `-p 9` | **abort** |
| `-p 256 -ub 16` | abort |
| `-p 256 -ub 8 -b 8` | ok, 331.6 t/s |

`turbo3/q8_0`, `turbo3/turbo3`, `q8_0/q8_0`, `turbo4/q8_0`, `turbo2/q8_0` all abort; only `f16/f16` prefills (1639 t/s). Pre-existing — `fca3093c9` does the same, so #295 neither caused nor fixed it.

Scope, to be exact: benchmark path only. My first read was "prefill with quantized KV aborts on RDNA4" and that is wrong — serving is fine at every prompt length I tried. `-ub 8 -b 8` works around it.

Worth flagging because it's a second `llama-bench` gap on this work, alongside jasstrong's note that TQ4max wouldn't load in the metrics-tree build. Between them, the standard measurement tool can't do prefill with quantized KV on RDNA4 and can't load some turbo weight quants — which may be part of why RDNA runtime evidence has been thin.

## On the entry itself

Two suggestions about keeping the gate useful, not about whether to add it.

**A threshold rather than a blanket shape ignore.** If `<128,2,TURBO3,Q8_0>` is listed outright, a later change taking it from 4 VGPR to 200 keeps the gate green. Since the goal is to start catching regressions again, "flag above N" preserves that on the shape most likely to move, and still goes green today at 259.

**`rwkv_wkv_f32` at 387 and `mul_mat_q` at 317 aren't covered by any of this.** They're larger than the turbo residuals and, as you say, not turbo kernels. Neither my data nor jasstrong's speaks to them. If "the surviving shapes" means all four, the gate goes green over two unexplained spills — I'd keep those separate.

One scope note on gfx942: everything above is RDNA. The `ubuntu-22-hip-quality-check` flag is CDNA, and none of us has that hardware. You just said you'd stop generalising from three RDNA parts — with jasstrong's run it's now four, but they're still all RDNA.

## Standing offer

gfx1201 and a pair of P100s here, both idle most of the time — RDNA4 and pre-Turing CUDA. Any sweep, census, or config you want, say the word.
