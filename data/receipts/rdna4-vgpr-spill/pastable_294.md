gfx1201 resource sweep against `f6124e914`, plus the runtime run you asked for.

**Provenance first:** the resource sweep was built at `f050a2501`, not the merge. The only delta between them touching flash attention is in `fattn-common.cuh` — `(void)` casts to silence `[[nodiscard]]` on `cudaStreamSynchronize`/`cudaFree` inside a destructor. No functional change, no register-allocation impact (the other file, `ggml-cuda.cu`, is the host-side RDNA2 stream-capture fix). So the spill numbers below apply to `f6124e914`. The runtime bench builds `f6124e914` directly.

RX 9070 XT, ROCm 7.2.4, `-DGGML_HIP=ON -DGPU_TARGETS=gfx1201 -DGGML_HIP_EXPORT_METRICS=On`, matched to my 2026-08-14 baseline run. Parser reproduces that baseline's published headline figures exactly, so the delta is like-for-like.

## Resource sweep

| | baseline `fca3093c9` | `f6124e914` | delta |
|---|---:|---:|---:|
| `flash_attn_ext_vec` kernels | 348 | 348 | — |
| FA kernels spilling | **98** | **41** | **−57** |
| worst FA VGPR spill | **735** | **357** | **−378** |

By head size: 256 → 55/33, 128 → 40/8, 64 → 3/0. **57 fixed, 0 newly spilling.**

## Your two questions

**1. Residual #3 — the gfx1100-only `<128,1,K=TURBO2,V=TURBO3>` at 36 VGPR.**

**Zero instances on gfx1201.** It does not occur here at all. On the evidence I have that reads as architecture-specific rather than a common pattern, which argues against signing anyone up for teaching the LUT paths to stride and reduce.

**2. Does `<128,2,turbo-K,*>` reach zero on gfx1201?**

No — it gets close and survives. Matches the scope correction you just posted:

| shape | before | after |
|---|---:|---:|
| `<128,2,TURBO3,TURBO3>` | 243 / 244 | 57 / 54 |
| `<128,2,TURBO2,TURBO3>` | 271 / 272 | 37 / 36 |
| `<128,2,TURBO4,TURBO3>` | 246 | 37 / 36 |
| `<128,2,TURBO3,Q8_0>` | 424 / 424 | 23 / 23 |

## Two things you may not have

**Bucket #1 is not "identical under both gates" here.** Present, 18 kernels, but they fell **698 → 57**, **681 → 57**, **661 → 36**. On gfx1030/1100/1103 they were already ≤22/62/23 before the fix; on gfx1201 they started at 625–735 and the gate cut them ~90%.

**A fourth bucket.** 19 of the 41 survivors are `Q8_0`-K pairs at D=256, ncols=2: `Q8_0`/TURBO2 (61, 60), `Q8_0`/F16 (40, 40), `Q8_0`/BF16 (32), `Q8_0`/TURBO4 (28, 25), plus `BF16`/`BF16` (13) and `F16`/`F16` (1). All byte-unchanged before→after. Same structural story as your Q4_0 residual — a non-turbo K path the gate doesn't reach — at a different type.

Bucket #2 confirmed as pre-existing: 4 kernels, byte-unchanged (357→357, 336→336, 226→226, 206→206).

**Scale context**, since gfx1201 wasn't in the original sweep:

| arch | spilling before→after | worst before→after |
|---|---|---|
| gfx1030 | 40 → 3 | 294 → 23 |
| gfx1100 | 42 → 10 | 421 → 37 |
| gfx1103 | 40 → 2 | 298 → 25 |
| **gfx1201** | **98 → 41** | **735 → 357** |

Largest absolute win of the four, from a starting point ~2.5× worse, and still carrying 4–20× the residual count of the others.

## Runtime

`llama-bench`, pure decode (`-p 0 -n 128`), `-fa 1`, `TURBO_AUTO_ASYMMETRIC=0`. Llama-3.2-3B-BF16 (D=128, GQA 3:1) so the `<128,2>` shapes are live and the auto-asymmetric gate can't fire. Two independent passes:

| KV | pass 1 (5 reps) | pass 2 (12 reps) |
|---|---:|---:|
| f16 *(control)* | −1.2 % | −1.1 % |
| turbo2 | +0.4 % | −0.3 % |
| turbo3 | +0.8 % | −0.9 % |
| turbo4 | +1.0 % | +1.0 % |

**Null result at ±1 %.** The two passes disagree in sign on turbo2 and turbo3, and this box shows intermittent 1–2 % (occasionally 6 %) variance between identical runs — some cells came back at ±1.7 even at 12 reps. I'm not claiming an improvement; I'm claiming there's no cost I can detect.

**So: the 23–57 VGPR residual doesn't buy back measurable decode throughput on RDNA4.** Your instinct to leave it alone holds up.

On the 12–31 % turbo2 `ncols=1` regression — **it does not reproduce here.** turbo2 was +0.4 % / −0.3 %. That one I'd treat as a real absence rather than a resolution limit, since 12–31 % is an order of magnitude above this machine's noise floor.

## Caveats

Decode only — no prefill, no long context, no batch >1. Throughput only, no fidelity gate. One card. And `ncols=2` arises through GQA packing rather than being pinned by a flag, so a shape-pinned microbenchmark would be stronger evidence than this.

D=256 was also measured; I'm not quoting deltas there because the 12-rep pass moved all four cells positive **including the f16 control the fix doesn't touch**, which reads as a machine-state offset between the two builds' runs rather than an effect of the commit.

Happy to re-run anything, pin specific shapes, or test other configs — it's the only gfx1201 here and it's free.
