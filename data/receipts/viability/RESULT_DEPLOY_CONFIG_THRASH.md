# A "deployment" config that passes every startup check and thrashes under load: 7/61

> **EXPLANATION SUPERSEDED 2026-09-08.** A direct probe found **no context ceiling**: prefix
> reuse is perfect from 32k to 262k with a static working set (0 resets, 0 budget-exceeded at
> ratio 3.12). The observations below stand; the causal account does not. The distinguishing
> variable is **prompt shape** — the agent run showed `0/14,390 tokens reusable`, which means
> its prefix is being altered rather than extended. See
> `RESULT_ENTRY_TIER_CEILING_FALSIFIED.md`.

**Date:** 2026-09-08 · **Node:** RX 9070 XT (gfx1201) · `buun-llama-cpp/build_rocm` `3823c9eb6`
**Model:** `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf`, 9.73 GiB (inline MTP head)
**Raw:** `qwen38_deploy_det01/`, `spark_raw/qwen_deploy_serve.log.gz`

Operator-requested reference config — what you would actually run on a 16 GB card:

```
-c 262144 -np 1 -fa on --kv-unified
-ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto
--spec-type draft-mtp
--reasoning-effort medium --min-p 0 --jinja
```

Sampling verified against `/props` as an exact match to Qwen3.8's card: temp 1.0, top_p 0.95,
top_k 20, min_p 0.0, presence_penalty 0.0.

**Not comparable** to `spark4b_det01` or the 35B baseline — different KV codec, context,
speculation and effort. A point of reference, as requested.

## Result: 7 PASS, 54 INFRA_ERROR

Passed the first 7 tasks. Everything from `t02_file_read/t03` onward timed out at 360–480 s.

## Root cause — configuration, not capability

```
vbr reset: cursor 128 and only 0/14390 prompt tokens reusable (< 0.25) — dropping
VBR budget 3183.27 MiB exceeded with the degrade order clamped at the --vbr-floor
```

**60 VBR resets. 10 budget-exceeded warnings. Zero of 14,390 prompt tokens reusable.**

262,144 context was requested on a card that could spare **3,183 MiB** for KV after a 9.73 GiB
model. The fitter accepted it at load by pricing KV at the `turbo2_tcq` floor — roughly
12.4 KiB/token against f16's 64. Under real load the budget was exceeded, VBR was already
clamped at its `--vbr-floor t2` with nowhere left to degrade, so it **reset the cache**. Each
reset forces a fresh full-schema prefill:

| | plain IQ3 (`-c 65536`, f16 KV) | this config |
|---|---:|---:|
| full-schema prefill | 16.3 s / 14,278 tok | **20.8 s / 14,244 tok** |
| mean prefill throughput | 628 t/s | **477 t/s** (−24%) |
| decode | 25.8 t/s | **19.4 t/s** (−25%) |

A multi-turn agent task paying 20.8 s of prefill per turn exhausts a 360 s budget in ~17 turns
**before generating anything**. That is the failure.

## Everything was green at startup

```
VBR dynamic: fitting with KV priced at the turbo2_tcq floor tier
VBR dynamic: KV VRAM budget 3183 MiB (auto, from remaining memory) — decode-time degrade controller armed
creating MTP draft context against the target model
initializing, n_slots = 1, n_ctx_slot = 262144, kv_unified = 'true'
speculative decoding context initialized
VBR_ARTIFACT_CAPTURE store ready attention_children=1 lanes=1
llama_server: listening on http://127.0.0.1:8090
```

Model loaded, MTP armed, artifact store ready, full context allocated, sampling exactly
on-card. **Nothing at load time indicated the config could not sustain a workload.** Third
instance today of `readiness-probes-lie` — the others being `--spec-type` defaulting to `none`
while logging "loading draft model", and `--model-draft` alone producing a silent no-op.

## The transferable lesson

**Size context to the VRAM you have, not to the model's maximum.** `--vbr-vram auto` fits what
it is asked to fit; it does not refuse an unwise request. Asking for the full 262k native
window left VBR at its floor with zero headroom, converting every cache miss into a full
re-prefill.

`--vbr-floor t2` compounded it: with the floor that low there was no further degrade step
available when the budget was exceeded, so the only remaining action was a reset. A higher
floor with a smaller context would have left the controller somewhere to go.

## What was NOT the cause

- **`reasoning_effort: medium` worked.** Early tasks generated 217–277 tokens against the
  `xhigh` run's 8,720. The effort ladder's 7× reduction reproduced.
- **MTP worked.** Draft acceptance 0.82 / 0.47, decode 32.9 t/s early (vs 25.8 without).
- **Sampling was correct** and verified against `/props`.
- **The server never crashed** — 19.4 t/s sustained to the end, no errors, GPU nominal.

Each component did its job. The combination over-committed VRAM.

## Follow-up worth running

Same config at `-c 32768` or `-c 65536`, which leaves the VBR controller headroom. That would
separate "this deployment shape is wrong" from "this context request was wrong" — currently
only the second is demonstrated.

## Scope correction 2026-09-08 — this card shares VRAM with a desktop

The desktop session holds **~2,266 MiB** (measured with no server resident). `--vbr-vram auto`
budgets from remaining memory, so a headless 16 GB card would have given this config
**~5,449 MiB** of KV budget instead of 3,183 — more than the 5,256 MiB that runs the same
suite cleanly without MTP.

**The failure documented here is therefore plausibly specific to a desktop-sharing card**, not
to the configuration. The transferable lesson stands ("size context to available VRAM"), but
"262k + MTP does not fit 16 GB" is **not** established — only "262k + MTP does not fit 16 GB
minus a desktop". Untested on a dedicated card.

## Discriminator run 2026-09-08 — 262k WITHOUT MTP also thrashes

Same config, `--spec-type draft-mtp` removed. KV budget rose 3,183 -> **5,256 MiB** as
predicted by `RESULT_MTP_VRAM_COST.md`.

| 262k config | pass | infra | budget exceeded | outcome |
|---|---:|---:|---:|---|
| **+ MTP** | 7/61 | 54 | 10 by task 7 | total collapse, never recovered |
| **no MTP** | 12 at task 23 | 11 | 4 | degrades, but recovers from individual timeouts |
| *(32k + MTP, for reference)* | *44/61* | *7* | *0* | *works* |

**262k is unusable on this card under sustained agentic load with or without MTP.** MTP makes
it dramatically worse — 54 infra errors against 11 — but it is not the root cause. An earlier
reading of this receipt called MTP the cause on the strength of the first 11 tasks; that was
premature and is corrected here.

## Not a memory leak — measured

VRAM sampled every 20 s for 77 minutes (232 samples, `spark_raw/vram_trace_262k_nomtp.txt`):

```
Q1 mean 13,144    Q2 13,358    Q3 13,390    Q4 13,470 MiB
drift Q2->Q4: +112 MiB  (<1% of a 13.4 GB working set; medians 13,361 -> 13,393)
```

The early rise is the KV cache filling; after that it oscillates in a band. RDNA4 has a history
of ROCm-side memory growth on this fleet, so this was worth ruling out explicitly. It is ruled
out for this build.

## The actual mechanism: entry-tier re-pricing, not steady-state bytes

The fitter's KV budget is nearly independent of the requested context — it is whatever VRAM
remains after weights:

| requested context | KV budget (no MTP) |
|---|---:|
| 65,536 | 5,410 MiB |
| 131,072 | 5,384 MiB |
| 262,144 | 5,256 MiB |

At the `turbo2_tcq` floor, 262k tokens need roughly 2 GB against 5.2 GB available — **it fits
with margin, and it loads.** But the reset message names the cost:

> `vbr reset: ... dropping the prefix; the full re-prefill re-enters at the entry tier`

**VBR enters at f16 and degrades under pressure.** At f16 a 262k context would want ~16 GB, so
every reset re-prices the entire prefix at the most expensive tier. Steady-state footprint is
cheap; re-entry is not, and it scales with context. That is why a config that allocates
comfortably still cascades: one timeout triggers a reset, the reset triggers an expensive
re-prefill, and at 262k that re-prefill is long enough to trigger the next timeout.

**Consequence for capacity planning:** "will it fit" arithmetic gives the allocation ceiling.
The usable ceiling under sustained load is lower, and the gap is governed by **entry-tier
re-prefill cost**, not by steady-state bytes. Where the boundary sits between 32k (works) and
262k (thrashes) is **unmeasured** — a 64k/128k sweep would find it.

## Limits

One run, one node, one context value. The claim that a smaller context fixes it is **untested**.
`t02_file_read/t03_read_paginated` failed in all three configurations tried today (Spark,
Qwen-xhigh, Qwen-deploy), so at least one of these tasks is hard independent of configuration.
