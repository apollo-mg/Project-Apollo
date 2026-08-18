No objection to the ignore entry for the RDNA4 shapes, but I have two pieces of data that change what the entry should say, and one scope flag.

## Decode does not launch ncols=2 on gfx1201

You wrote that `ncols=2` is a shape decode really launches, and that's what makes a residual there matter. I could check that rather than assume it. No `rocprof` on this box, but `AMD_LOG_LEVEL=4` prints every dispatch's `ShaderName` with the template arguments intact.

Build `f6124e914`, `-fa 1`, `TURBO_AUTO_ASYMMETRIC=0`, types per the fork's `ggml.h` (`8=Q8_0 43=TURBO2 44=TURBO3 47=TURBO4`):

| config | kernel launched | count |
|---|---|---:|
| D=128, GQA 3:1, decode | `flash_attn_ext_vec<128, 1, TURBO3, Q8_0>` | 84 |
| D=256, GQA 4:1, decode | `flash_attn_ext_vec<256, 1, TURBO3, Q8_0>` | 40 |
| D=256, GQA 6:1, decode | `flash_attn_ext_vec<256, 1, TURBO3, Q8_0>` | 80 |
| D=128, decode at depth 4096 | `flash_attn_ext_vec<128, 1, TURBO3, Q8_0>` | 112 |
| D=128, turbo3 symmetric | `flash_attn_ext_vec<128, 1, TURBO3, TURBO3>` | 84 |

Every one is `ncols=1`. Three GQA ratios, two head dims, and the packing factor never moves the VEC `ncols`. Depth changes the count (84 → 112) and not the shape, which is the control working.

So on gfx1201 ordinary token generation doesn't reach the `<128,2,…>` class at all. That argues *for* your ignore entry rather than against it — the shape is less live than the premise assumed, at least here. What I can't tell you is what does launch `ncols=2`; speculative decoding and multi-sequence batching are the obvious candidates and `llama-bench` can't produce either.

If it's useful I can run the same census on any config you name.

## `llama-bench` can't prefill with quantized KV on this card

Found while trying to add a prefill regime so the runtime null wasn't decode-only.

Same build, `llama-bench` vs `llama-server`:

| path | config | result |
|---|---|---|
| `llama-bench` | `-p 256 -n 0`, any quantized KV | ROCm error → abort, `ggml-cuda.cu:109` |
| `llama-server` | ~2000-token prompt, `turbo3`/`q8_0` | fine, coherent output |

The threshold is exact, and it lands where your HIP branch in `ggml_cuda_get_best_fattn_kernel` puts the VEC/TILE boundary:

| | |
|---|---|
| `-p 8` | ok |
| `-p 9` | **abort** |
| `-p 256 -ub 16` | abort |
| `-p 256 -ub 8 -b 8` | ok, 331.6 t/s |

`turbo3/q8_0`, `turbo3/turbo3`, `q8_0/q8_0`, `turbo4/q8_0`, `turbo2/q8_0` all abort. Only `f16/f16` prefills (1639 t/s). Pre-existing — `fca3093c9` does the same, so #295 neither caused nor fixed it.

Worth flagging because `llama-bench` is how these codecs get measured. On RDNA4 it can't produce a prefill number for any quantized KV type, which may be part of why the runtime evidence you're after from an RDNA part doesn't exist. `-ub 8 -b 8` works around it.

To be clear about scope: this is the benchmark path only. My first read was "prefill aborts with quantized KV on RDNA4" and that's wrong — serving is fine at every prompt length I tried.

## On the ignore list itself

Two suggestions, both about keeping the gate useful rather than about whether to add the entry.

**Scope the justification to RDNA4.** My numbers are gfx1201, decode, one model, ±1%. The `ubuntu-22-hip-quality-check` flag is gfx942, which is CDNA — different arch, and I have no CDNA hardware to extend the measurement to. You just wrote that you'll stop generalising from three RDNA parts; I'd rather not have you generalise from one RDNA part on my account. Happy for the entry to cite my numbers for gfx1201 and stand on its own reasoning for gfx942.

**Consider a threshold instead of a blanket shape ignore.** If `<128,2,TURBO3,Q8_0>` is listed outright, a future change taking it from 4 VGPR to 200 keeps the gate green. Since the stated goal is to start catching regressions again, an entry of the form "flag above N" preserves that on the shape most likely to move, and still goes green today at 259.

**And the two big ones aren't covered by anything I measured.** `rwkv_wkv_f32` at 387 and `mul_mat_q` at 317 are larger than the turbo residuals and, as you say, not turbo kernels. Nothing in my data speaks to them. If "the surviving shapes" means all four, the gate goes green over two unexplained spills — I'd keep those separate from this entry.

## Standing offer

gfx1201 and a pair of P100s here, both idle most of the time. That's RDNA4 and pre-Turing CUDA, which between them seem to be the two ends least covered by CI. Say the word on any sweep, census, or config and I'll run it.
