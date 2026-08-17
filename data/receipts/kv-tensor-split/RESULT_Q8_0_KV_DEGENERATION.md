# `q8_0` KV produces pure token collapse under `-sm tensor` on 2x P100 — 16/16, first request

**2026-08-16.** Node `.73`, dual Tesla P100 (sm_60), 1063 MHz / 150 W.
Build **`buun_vbr` `a8e5b5a38`** ("ggml-backend-meta: allow sharded + full-width MIRRORED
binary ops"), 805 commits ahead of upstream `b9637`.
Model `unsloth-Qwen3.8-27B-Q6_K.gguf`. All arms `-sm tensor -ts 1,1 --spec-type draft-mtp`,
`temperature 1.0 / top_p 0.95 / top_k 20`, `n_predict 2048`, `cache_prompt:false`,
8 sequential requests per arm, default slots and cache-reuse.

## Result — a clean 2x2

| | f16 KV | `q8_0` K+V |
|---|---|---|
| **ctx 16384** | **8/8 clean** | **8/8 DEGENERATE** |
| **ctx 40960** | **8/8 clean** | **8/8 DEGENERATE** |

Failure signature is identical every time: `len=2048 maxrun=2048 uniq=1` — the entire
2048-token response is **one character repeated**. Not degraded quality. Total collapse, on the
**first request**, deterministically.

**Context length is exonerated.** 40960 with f16 is as clean as 16384 with f16.

## What is NOT yet established

All four arms carried **both** `-sm tensor` **and** `--spec-type draft-mtp`. So the honest claim
is "`q8_0` KV collapses in combination with tensor split and MTP on this build", not "`q8_0` KV
is broken on Pascal". Mark runs `-ctk q8_0 -ctv turbo4` daily on this node without trouble,
which is direct counter-evidence to the general version. A pin run (`kv_pin.sh`, P1–P6) is
separating: K-only, V-only, `-sm layer`, no-MTP, and his turbo4 pair.

## Mechanism candidates, and one already falsified

**Falsified — block/head misalignment at the shard boundary.** Qwen3.8-27B has
`num_key_value_heads: 4` (splits 2/2 evenly at `-ts 1,1`) and `head_dim: 256` (8 whole `q8_0`
32-element blocks per head). Nothing straddles a boundary. The simple alignment story is out.

**Live.** A defect in the quantized-KV path under tensor sharding. `f16` has no block structure
to shard, which is consistent with f16 being clean at the same split mode and context.

**Context.** `head_dim: 256` is unusual (most models use 128) and this codebase family has form
there — `rdna4-vgpr-spill/RESULT_GFX1201.md`: *"RDNA4 spills too, and worse, and not only at
head size 256."* Not an explanation by itself, since f16 at the same head_dim is fine.

**Timeline.** `-sm tensor` on this fleet is two days old (`RESULT_P100_SM_TENSOR.md`, 08-14).
Before that `-sm layer`, which does not shard the cache. The bug may be long-standing and
simply never exercised here.

## Consequence for an existing finding

`RESULT_P100_SM_TENSOR.md` measured `-sm tensor` at **1.62x over a single P100**. That stands —
it was measured at f16. But it needs a constraint attached: **on this build the 1.62x is only
available with f16 KV**, so the split speedup and a quantized cache cannot currently be
combined. Anyone wanting both must choose.

## A methodology note worth keeping

The degeneracy detector initially flagged arm C (40960/f16) as failing: `maxrun=52 uniq=76` on
an 8674-char response, against a `maxrun>40` threshold. Inspecting the text showed a perfectly
normal answer whose longest run was a table rule. Had the flag been trusted, context length
would have been wrongly implicated and the isolation broken. Recorded as `FAILURE_MODES.md`
**AFM-15**; threshold raised to `>200` before the pin run inherited it.

## Reporting status

Not yet reported to buun — pending the pin result, which decides whether this is
"tensor split x quantized KV" (a specific, patchable interaction) or "the codec on this build"
(a bisect request). `.194` carries a **different** `buun_vbr` commit (`1abf2d28c`) and both
forks, so it can serve as both a second-commit check and a turboquant cross-test — but it is
occupied by the HumanEval+ ladder (~30 h/cell, mid-cell) for now.
