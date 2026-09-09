# MTP draft acceptance drops to 0.000 permanently after the VBR degrade order clamps at --vbr-floor

**Build:** `3823c9eb6` · RX 9070 XT / ROCm · `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf`
**Flags:** `-ngl 99 -c 32768 -np 1 -fa on --kv-unified -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto --spec-type draft-mtp --reasoning-effort medium --min-p 0 --jinja`
**Workload:** sustained multi-turn agent load (hermesbench, 61 tasks). KV VRAM budget resolved to 4433 MiB.

## Summary

Under sustained multi-turn load, MTP draft acceptance collapses to **exactly 0.000** and `mean len` to **1.00**, permanently, for every subsequent request on the slot. Decode drops **~2.7x**. A server restart fully restores it. The transition coincides with the VBR degrade order clamping at the floor.

The server keeps *generating* drafts that can never be accepted, so it pays full draft cost for zero benefit — the GPU sits power-pegged at full clocks and normal temps while producing half the tokens.

## The transition

```
24.2  slot release: task 12975 | stop processing: n_tokens = 21481, truncated = 0
24.2  VBR_RETIER_PREFLIGHT owner=server_checkpoint_restore result=fits
        watermark=21504 needed=199360512
24.4  W prepare_with_slots: VBR budget 4433.27 MiB exceeded with the degrade order
        clamped at the --vbr-floor (projected 132.12 MiB at 14848 cells)
```

A 21,481-token request drove the retier watermark to **21,504 cells** (every prior request sat at 14,336–19,200). VBR could not fit its budget even after degrading to `t2`, so the degrade order clamped with nowhere further to go.

## Separation is clean

| | n | mean acceptance | min |
|---|---|---|---|
| before the clamp | **80** | 0.682 | **0.444** |
| after | 3 | 0.104 | 0.000 |

Not one of the 80 pre-clamp requests fell below **0.444**. Every post-clamp value is **<= 0.312**. No overlap. Further clamps at min 32.9, 38.9, 65.8.

## Restart fully reverses it

Identical prompt, identical flags, identical binary — only server uptime differs:

| | decode | acceptance | mean len |
|---|---|---|---|
| collapsed, min 32.9 | 22.04 t/s | **0.000** (0/187) | 1.00 |
| collapsed, min 38.9 | 22.05 t/s | **0.000** (0/187) | 1.00 |
| **fresh server** | **59.62 t/s** | **0.933** (70/75) | 3.80 |
| **fresh server** | **61.63 t/s** | **0.972** (70/72) | 3.92 |
| **fresh server** | **60.65 t/s** | **0.933** (70/75) | 3.80 |

`mean len` going to 1.00 is the tell: the draft head stops proposing multi-token continuations entirely, and the single token it does propose is always rejected.

## For scale — 0.000 is off the map

ISTA's published MTP figures for this same quant family (llama.cpp speed-bench, 3 draft tokens) give a **mean of 54.2%** with the **lowest bar across 11 categories x 4 quants at ~49%**. Zero doesn't appear anywhere in the vendor's own characterisation.

## Ruled out

- **`CHECKPOINT_ATTN_ONLY_TRIM p0=NNNN target=1 draft=0`** — looked like the obvious culprit (draft context not restored alongside target), but it fires **47 times from minute 0.29**, always `draft=0`, and acceptance stayed healthy for 80 requests afterwards. Constant, not causal.
- **`vbr reset ... 0/14,2xx prompt tokens reusable`** — also constant from min 0.6, before and after.
- **Request size alone** — a single 20,901-token request on a *fresh* server does **not** reproduce it. Watermark stays at **256**, acceptance holds at 0.939.
- **Uptime alone** — the fresh server sat idle-then-probed without collapsing.

## What appears to drive it: accumulated context checkpoints

| | checkpoints created | watermark reached | acceptance |
|---|---|---|---|
| collapsed agent run | **120** | 21,504 | 0.68 -> 0.000 |
| fresh + one 20,901-token request | **4** | 256 | 0.972 -> 0.939 |

KV budget was effectively identical (4433 vs 4441 MiB). Multi-turn conversations create checkpoints (`created context checkpoint N of 32`), they accumulate, the watermark climbs, and eventually the budget cannot be met even at the floor.

That also explains why it needs ~25 min of *agent* load specifically, why one big request can't reproduce it, and why the wall landed at different task indices in two separate runs.

## Repro

Sustained **multi-turn** load against the flags above. Watch `created context checkpoint N of 32` accumulate and `VBR_RETIER_PREFLIGHT ... watermark=` climb. When `prepare_with_slots` reports the floor clamp, acceptance goes to 0.000 and stays there. Restart restores it.

## What we have NOT tested — please weight accordingly

- **No static-KV control.** We have not run `-ctk f16 -ctv f16` under the same load. So while the trigger is a VBR budget event, **we have not isolated VBR from the checkpoint machinery** — it could be checkpoint accumulation alone, with VBR only the thing that reports it first. This is the obvious next arm and we can run it.
- **Not tested against upstream llama.cpp.**
- This build **predates `a56eeef5`** (our 9070 box is on `3823c9eb6`, Sep 3). We verified `a56eeef5` separately on dual-P100 for the tensor-split cache fix — that worked, 4010 -> 4 tokens on pass 2, 19.1x. Untested whether it touches this.
- Single hardware (RDNA4/ROCm), single model, `-np 1`.

## Possibly relevant knobs we haven't swept

`--ctx-checkpoints` (default 32), `--checkpoint-min-step` (8192), `--vbr-reclaim-floor`, `--vbr-reset-keep-frac`. Happy to run any sweep that would be useful.
