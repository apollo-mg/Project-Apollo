# A 180B model runs on four P100s at ~9 tok/s — but not by the mechanism the card advertises

**2026-08-28**, `.194`: 4x Tesla P100-PCIE-16GB (sm_60, 64 GiB VRAM), 60 GiB DDR4-2133,
2x Xeon E5-2650 v3, 1063 MHz / 150 W. `TheTom/llama-cpp-turboquant` PR #324 @ `d74823a0c`
(qwen4exp), built for sm_60. Weights: `Qwen3.8-Flash-Next-UD-IQ4_XS`, 87.2 GiB, 3 shards.
Pre-registration: `PREREG_FLASHNEXT_OFFLOAD.md` (written before the weights were downloaded).

## SPLIT MODE CAVEAT — every number below is pipelined layer-split

**All Flash-Next throughput in this receipt was measured with llama.cpp's DEFAULT split mode,
which is `layer` — "split layers and KV across GPUs (pipelined)".** No `-sm` flag was passed;
only `-fit off -ngl N`. Confirmed live: during generation `nvidia-smi` reads
`0% 0% 90% 0%` — one card working while three idle.

**These are therefore a FLOOR, not a ceiling.** `-sm tensor` parallelises across devices and is
known-good on this hardware for other models: the llama-swap production entry on `.73` uses
`-sm tensor -ts .85,1.15`, and `RESULT_VBR_FIDELITY.md` used `-sm tensor -fit off` on 2x P100.

This also makes the comparison against the 13.8 tok/s `Qwen3.8-27B-Q6_K` reference **unfair in
both directions**: that reference was measured with `-sm tensor`. A like-for-like Flash-Next
number needs re-measuring under tensor split, which has not been done.

## Headline

| configuration | throughput |
|---|---:|
| CPU only (`-ngl 0`), 180B entirely on DDR4-2133 | **0.74 tok/s** |
| **`-ngl 44`**, 44/48 layers on GPU, PLE table + 4 layers on CPU | **~9.0 tok/s** |
| *reference*: `Qwen3.8-27B-Q6_K` fully resident, 2x P100 | *13.8 tok/s* |

Warm decode across 6 runs: 8.59, 8.68, 8.99, 8.99, 9.76 tok/s (plus 6.50 and 2.92 while the
page cache warmed). **~12x the CPU floor, ~65% of a fully-resident 27B.** Every run answered
`17 x 23` correctly.

VRAM at `-ngl 44`: 14769 / 13905 / 14313 / 13995 MiB — device 0 carries ~0.9 GiB more because
the non-layer tensors land there.

Prefill measured at **~59 tok/s** on a 659-token prompt.

## Prediction scoring

| # | prediction | conf | outcome |
|---|---|---:|---|
| P1 | beats the 13.8 tok/s 27B baseline | 0.60 | **FAILED** — 9.0 tok/s, 65% of it |
| P2 | placement beats naive offload by >2x | 0.75 | **UNTESTABLE** — `-ot` had no effect (below) |
| P3 | KV < 1.5 GiB at 32k | 0.70 | **NOT MEASURED** — ran at 4k; not attempted at depth |
| P4 | runs on sm_60 without new kernels | 0.55 | **CONFIRMED** — and with real weights, not just `test-llama-archs` |
| P5 | prompt processing not competitive | 0.65 | **CONFIRMED** — ~59 tok/s prefill is poor for this class |

**P1 is the interesting failure.** It is close enough that the framing matters: a 180B model
with a third of its weights in system RAM reaching 65% of a resident 27B is a *good* result that
still does not clear the bar as registered. The bar was the right one to set — "competitive
with full-GPU 27B speeds" was the actual question — and the honest answer is *nearly, but no*.

## The mechanism claim does not survive contact

The card says embedding-based scaling is "more amenable to offloading than MoE", and the tensor
map supports it structurally:

```
26.82 GiB  x1    per_layer_token_embd.weight   <- ONE tensor, sparsely read
55.43 GiB  x144  blk.N.ffn_{down,gate,up}_exps <- streamed, 10 of 512 experts per token
 ~5   GiB        attention / SSM / hyper-connections
```

The intended experiment was to place the PLE table on CPU and keep all experts resident,
then compare against naive layer offload of equal byte volume. **That comparison could not be
run: `-ot` tensor overrides had no effect on placement.** Five attempts —

| attempt | override | device-0 request |
|---|---|---|
| `-ngl 99` | none | 16847.21 MiB |
| `-ngl 99` | `per_layer_token_embd=CPU` | **16847.21 MiB** |
| `-ngl 99` | `+ 12 layers of experts to CPU` | **16847.21 MiB** |
| `-ngl 99` | `+ token_embd, output to CPU` | **16847.21 MiB** |

Byte-identical every time (`17665582848`), while `llama_model_loader` did print its
"tensor overrides to CPU are used with mmap enabled" warning — so the flags parse and are
ignored. By contrast `-ngl` scales cleanly: measured 12474 / 22296 / 32494 MiB at N = 8 / 16 / 24,
i.e. **~1250 MiB per layer over a ~2650 MiB base**, which predicts the `-ngl 44` ceiling
correctly (device 0 = total/4 + ~1.1 GiB of non-layer tensors, against 16384 MiB of card).

So the ~9 tok/s above is achieved by **ordinary layer offload**, not by the placement strategy
the architecture is supposed to reward. Whether the PLE-on-CPU strategy is better remains
**unknown**, and needs either a working `-ot` on this arch or an equivalent knob.

## Memory-tier telemetry — what llama.cpp does, and what it gets wrong

### VRAM is exactly linear in resident layers

| `-ngl` | VRAM (MiB) | `2650 + 1250N` | error |
|---:|---:|---:|---:|
| 8 | 12,474 | 12,650 | +1.4% |
| 12 | 17,388 | 17,650 | +1.5% |
| 16 | 22,296 | 22,650 | +1.6% |
| 24 | 32,494 | 32,650 | +0.5% |
| 36 | 47,190 | 47,650 | +1.0% |
| 44 | 56,982 | 57,650 | +1.2% |

**VRAM ~= 2,650 + 1,250 x N MiB.** The model predicts every measured point to within ~1.5%,
and correctly predicts the `-ngl 44` ceiling: device 0 takes `total/4` **plus ~1.1 GiB of
non-layer tensors** (`token_embd` 0.63 + `output` 0.49), which is what pushes it past 16,384 MiB
at `-ngl 45+`. Capacity planning on this arch is therefore a one-line calculation.

### Throughput is linear in resident layers — above a regime boundary

| `-ngl` | tok/s | s/token | marginal s/token per layer |
|---:|---:|---:|---:|
| 0 | 0.74 | 1.3514 | — |
| 12 | 2.39 | 0.4184 | **0.0778** |
| 24 | 3.36 | 0.2976 | 0.0101 |
| 36 | 5.09 | 0.1965 | 0.0084 |
| 44 | ~9.00 | 0.1111 | 0.0107 |

**From `-ngl 12` upward each resident layer is worth a near-constant 0.0097 +/- 0.0011 s/token.**
The `0 -> 12` figure is 8x larger, but it is **not** evidence that early layers matter more: it
is the boundary between *no GPU participation at all* and *any*. `-ngl 0` runs a different path.
Treated as a layer-count effect it would badly mislead placement decisions.

**Falsifiable check, scored:** after measuring 12 and 24, the linear model predicted **5.5 tok/s
at `-ngl 36`**. Measured **5.09** — the model runs **7.5% optimistic**, good enough for capacity
planning and not good enough to quote as a performance figure.

Caveat: the `-ngl 0` point used a different prompt and was measured cold; 12/24/36 share a
prompt and include two warm-up calls, so those three are internally consistent.

### Two placement mechanisms that do not work on this arch

1. **`-ot` tensor overrides are silently ignored** (five attempts, byte-identical device-0
   request). Only `-ngl` moves anything.
2. **The compute-buffer estimator is wrong for `qwen4exp`.** Every device logged a mismatch at
   `-ngl 44`:
   ```
   CUDA1 compute buffer size of 146.7911 MiB, does not match expectation of 139.0157 MiB
   CUDA2 149.8038 vs 144.0157 | CUDA3 149.8038 vs 144.0159
   CUDA_Host  29.7715 vs  14.8692     <- off by 2x
   ```
   That estimator is what auto-fit uses to decide how much headroom to leave, so it will
   mis-size allocations on this architecture. Probably the same code path that produced
   `common_fit_params: vector::_M_range_check` when a relaunch raced partly-occupied VRAM.

## What this does NOT establish

- One quant (IQ4_XS), one node, one context depth (4k), short prompts.
- n=6 warm decode samples on a trivial prompt; no long-generation or long-context measurement.
- The 13.8 tok/s reference is **2x P100 serving a 27B**, this is **4x P100 serving a 180B**.
  It answers "what can this box serve", not a controlled per-GPU comparison.
- Nothing here separates "the offload penalty" from "the architecture's own speed" — that needs
  a fully-resident run, which 64 GiB of VRAM cannot host at this quant.

## Reproduce

```
GGML_CUDA_ALLREDUCE=internal ./build_sm60/bin/llama-server \
  -m Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf \
  -c 4096 -np 1 -fit off -fa on --jinja -ngl 44 --host 127.0.0.1 --port 8087
```
`GGML_CUDA_ALLREDUCE=internal` is mandatory on this node. `-ngl 45+` OOMs device 0.
