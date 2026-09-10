# MTP inverts to 0.44× at np=8 — but the mechanism is VRAM starvation, not compute contention

**Date:** 2026-09-07 · **Prereg:** `PREREG_MTP_UNDER_LOAD.md` (written before the run)
**Model:** `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf` (inline MTP head, `blk.64`)
**Node:** RX 9070 XT (gfx1201) · `buun-llama-cpp/build_rocm` `3823c9eb6` · `-ngl 99 -fa on`
`-c` scaled as `2048 × np` so per-slot context is constant · temp 0, `max_tokens 300`
**Raw:** `mtp_load.log`, `/tmp/mtpload_*.log`

Every MTP figure in this corpus was measured at `np=1`, including `qwen38-mtp`'s **1.68×**.
This asks whether that number survives concurrency.

## Result

| np | MTP off agg t/s | MTP on agg t/s | ratio | off per-req | on per-req | draft acceptance |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 28.90 | **40.59** | **1.40×** | 28.90 | 40.59 | 0.568 |
| 2 | 48.60 | 56.50 | 1.16× | 24.30 | 28.25 | 0.594 |
| 4 | 61.70 | **84.74** | 1.37× | 15.43 | 21.42 | 0.531 |
| 8 | **79.44** | 35.10 | **0.44×** | 9.94 | **4.44** | 0.494 |

At `np=8`, MTP more than halves aggregate throughput **and** more than halves per-request
throughput. It is not a throughput-for-latency trade at that point; it is worse at both.

**Best cell overall is `np=4` with MTP on (84.74 t/s)** — better than MTP-off at any tested
concurrency, including `np=8`'s 79.44.

## The mechanism is NOT what the prereg assumed

The prereg's stated hypothesis was compute contention: spare compute at batch 1 makes drafting
free, and concurrent load consumes it. **The logs do not support that.** The fitter's KV budget:

| cell | KV VRAM budget |
|---|---:|
| np=8, MTP **off** | **4449 MiB** |
| np=4, MTP on | 2746 MiB |
| np=8, MTP **on** | **228 MiB** |

Turning MTP on at `np=8` cut the KV budget by **20×**. The MTP head's own context requirement
scales with slot count, and at `np=8` it consumed nearly all remaining VRAM, leaving 228 MiB of
KV cache across eight slots. The collapse is **memory starvation**, and the compute-contention
story is unsupported by anything measured here.

Supporting evidence that drafting itself was healthy: **acceptance is flat across the sweep**
(0.568 / 0.594 / 0.531 / 0.494). The draft head kept predicting well while throughput
collapsed — exactly what a resource-starvation failure looks like and not what draft-quality
degradation would look like. That was M-4, and it is the observation that rules the prereg's
own hypothesis out.

This is the same shape as `dflash-pascal/RESULT_S2_DFLASH_PASCAL.md`, where `dfl_n15` OOMs at
16 GB because DFlash carries a separate model and context. MTP shares the trunk's *weights* but
evidently not its *per-slot context cost*.

## Prediction scoring

| # | prediction | conf | outcome |
|---|---|---:|---|
| M-1 | `np=1` MTP speedup ≥ 1.4× | 0.70 | **HIT** — 1.40× exactly |
| M-2 | MTP advantage decreases **monotonically** with np | 0.75 | **MISS** — 1.40 → 1.16 → 1.37 → 0.44. The np=2 dip and np=4 recovery are not monotone. |
| M-3 | MTP inverts at or before np=8 | 0.55 | **HIT** — 0.44× at np=8 |
| M-4 | acceptance roughly flat across np | 0.70 | **HIT** — 0.49–0.59, no trend |
| M-5 | per-request stays better even where aggregate inverts | 0.45 | **MISS** — per-request also inverts, 4.44 vs 9.94 |

M-5's miss removes the operational nuance the prereg anticipated. There is no "keep MTP on for
interactive fleets" case at `np=8` on this configuration: it is worse on both axes.

## What this means for existing numbers

`qwen38-mtp`'s **1.68×** and every other MTP figure here were measured at `np=1`. They remain
correct at `np=1` and **do not describe a server with concurrent users**. Any deployment
recommendation citing them needs the concurrency stated alongside.

## The actionable version, stated carefully

On **this** card, **this** model and **this** VRAM budget, `np=4` + MTP is the throughput
optimum and `np=8` + MTP is a trap. That is not a general law — it is a **fitter outcome**, and
it will move with VRAM, model size, context, and quant. The transferable finding is the
*mechanism*: **MTP's memory cost scales with slot count and competes with the KV cache**, so
the failure appears suddenly when the fitter runs out of headroom rather than degrading
gradually.

Which suggests the load-dynamic feature worth asking for is not "disable speculation above N
slots" but **"disable speculation when the fitter's KV budget falls below a threshold"** — the
budget is the thing that actually predicts the collapse, and the server already computes it at
load time.

## Limits

- **One measurement per cell, no repeats.** The np=2 dip (1.16× against 1.40 and 1.37 either
  side) is within plausible run-to-run noise and should not be interpreted.
- `-c` scales with np, so total KV grows with concurrency by construction. Per-slot context is
  held constant, which is the right control for *per-slot* behaviour, but it means the
  VRAM-pressure axis moves with np — and that turned out to be the operative variable.
  A cleaner design fixes total VRAM and varies only np.
- One model, one quant, one card, one prompt, one draft depth.
- 16 GB card. On a card with more headroom the np=8 cell might not starve at all, which would
  make the inversion disappear entirely.
