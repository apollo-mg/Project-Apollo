# Pre-registration — VBR on Qwen3.8-27B at 2/3 bpw, gfx1201, post-fix

**2026-09-03, written before the run.** buun-llama-cpp `3823c9eb6` (contains `424c3361e`,
the Turbo KV prefill dispatch fix verified in `../kv-tensor-split/RESULT_TURBO_FIXED_AT_HEAD.md`).
RX 9070 XT 16 GiB. Models: `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` (3.05 bpw) and
`-IQ2_XS-mtp` (2.58 bpw), ISTA-DASLab GSQ-RCO.

This is the first VBR test on this model class since the turbo collapse was fixed. Until
today every turbo tier was degenerate on this card, so VBR had no safe rung below f16 and
could not be meaningfully exercised.

## Known structure (measured today, `../gguf-librarian/RESULT_DIRK_GSQ_RCO_HYBRID.md`)

Qwen3.8-27B is a hybrid: `full_attention_interval 4`, **16 of 65 layers carry KV**
(blk 3,7,…,63 plus MTP blk 64), `head_count_kv 4`, `key/value_length 256`.
**KV = 64 KiB/token at f16**, so 32,768 ctx = 2.0 GiB.

The baked degrade table (`llama-vbr-degrade-orders.inc`) keys on `(arch, n_layer_all)` and
has `{LLM_ARCH_QWEN35, 64, vbr_order_q27}`. Qwen3.8-27B is `n_layer_all = 65` (MTP), so the
exact key misses; a second pass matches on the exact KV-layer-id set.

## Predictions

| # | prediction | conf |
|---|---|---|
| P1 | VBR resolves a degrade order via the **KV-layout fallback** (log line "arch + KV-layout matched"), not the exact `(arch, n_layer)` match and not the generic warning | 0.65 |
| P2 | With `--vbr-vram auto` on a 16 GiB card at `-c 32768`, VBR **never degrades** — budget is ample, kv stays at the f16 entry tier. A pass here proves nothing about VBR quality | 0.80 |
| P3 | With a forced small budget (`--vbr-vram 512MiB` at `-c 32768`, vs 2.0 GiB needed at f16), the server starts and serves, i.e. it **actually degrades** rather than failing to allocate | 0.75 |
| P4 | Under forced degradation, output stays coherent and the 3-term copy probe passes 3/3 — no repeat of the pre-fix collapse | 0.70 |
| P5 | IQ2_XS (2.58 bpw weights) degrades *quality* more than IQ3_XXS under the same KV budget, but neither collapses | 0.55 |
| P6 | The MTP layer (blk 64) takes a KV slot, making 17 KV layers against the table's 16, which would break the KV-layout set-equality match and fall through to generic | 0.30 |

**P1 and P6 are mutually exclusive as stated** — if 17 KV layers are allocated, the set match
fails and P1 is false. Recording both because I do not know whether the nextn layer gets a
cache slot, and the log line settles it either way.

**Falsification that matters:** if VBR under a forced budget produces the 1200-token
empty-content runaway, then `424c3361e` fixed the explicit `-ctk turbo*` path but not the
VBR transcode path, and the fix is incomplete for buun's headline feature.

## Method

`-c 32768`, `-fa on --jinja --kv-unified -np 1`, temp 0, seed 42, K=3.
Arms: (a) `-ctk f16 -ctv f16` control; (b) `-ctk vbr -ctv vbr --vbr-vram auto`;
(c) `-ctk vbr -ctv vbr --vbr-vram 512MiB`; (d) same at `--vbr-vram 256MiB`.
Probes: the 3-term `json_schema` copy task and a 2,133-token free-prose prompt.
Scored on `finish=stop` **and** all three terms character-exact. Degradation confirmed by
postcondition (serving 32k in a budget smaller than f16 requires), not by a log line alone.
