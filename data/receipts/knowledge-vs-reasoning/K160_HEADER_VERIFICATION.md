# DS4-Flash K160 — card claims verified from the file, over 8.4 MB

**Date:** 2026-08-07. `jabbatheduck/DeepSeek-v4-flash-mini`,
`DeepSeek-V4-Flash-REAP-IQ2XXS-w2Q2K-AProjQ8-OutQ8-chat-v2.gguf` (57.3 GB).
Read via HTTP range requests with `gguf_probe_url.py` — **8.4 MB fetched, no download.** Same
technique that established the Maple ternary structure without pulling a shard.

## Property, not label — verified structurally

| claim | source | verified |
|---|---|---|
| 160 of 256 routed experts retained | card | `deepseek4.expert_count = 160`, and `blk.0.ffn_gate_exps.weight` shape `[4096, 2048, 160]` |
| top-6 routing preserved | card | `deepseek4.expert_used_count = 6` |
| `IQ2_XXS` experts, `Q2_K` down-proj | card | **86 IQ2_XXS + 43 Q2_K over 43 blocks** = exactly 2/layer (gate, up) and 1/layer (down) |
| Q8 attention-proj / output / shared | card | 366 `Q8_0` |

Full histogram: `F32` 536, `Q8_0` 366, `F16` 251, `IQ2_XXS` 86, `Q2_K` 43, `BF16` 43, `I32` 3.
1328 tensors, 60 KV, gguf v3, `general.architecture = deepseek4`, 43 blocks,
`expert_gating_func = 4`, `expert_weights_norm = True`, `expert_weights_scale = 1.5`.

**Every structural claim on the card checks out.**

## The imatrix question — narrowed, not settled

jabba's own reproduction script writes a **template** at step 0 named
`DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-OutQ8-chat-v2.gguf` and the **final imatrix-quantized**
artifact at step 3 as `...-chat-v2-imatrix-0731.gguf`. The published file carries the *template*
naming pattern (plus a `REAP-` prefix), not the final one.

- **`quantize.imatrix.*` KVs present: 0.** But those are a **llama.cpp convention** and this was
  built with `antirez/ds4` gguf-tools. **Absence is not evidence.** A positive would have been
  conclusive; a negative is not.
- Type histogram cannot distinguish the two: step 0's template is itself produced by the
  quantizer with the same recipe.
- File size cannot distinguish them either — an imatrix changes which values land where, not the
  block layout.

**The only cheap definitive test is on jabba's side:** `sha256sum` his local
`...-chat-v2-imatrix-0731.gguf` and compare to the published file's LFS hash. He has both
`deepseek-v4-flash-reap-imatrix.gguf` and the 1.5M-token
`DeepSeek-V4-Flash-chat-v2-routed-moe-ds4-1p5m.dat`, so the pipeline plainly ran; naming drift on
upload is the likely explanation. Worth confirming rather than assuming, because the two artifacts
are indistinguishable from outside and one is materially worse.

## Why this is recorded

The campaign's standard is *property, not label* — read capability-relevant structure off the
runtime or the file, never off a model card. This is the cheapest possible instance: four card
claims confirmed for 8.4 MB and no GPU time. `gguf_probe_url.py` generalizes to any remote GGUF and
is the right first step before committing disk to a download.
