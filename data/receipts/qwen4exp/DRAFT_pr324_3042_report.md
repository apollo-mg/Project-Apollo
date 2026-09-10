# DRAFT — PR #324 reply for `3042c600b`. For Mark to review. NOT POSTED.

---

Synced to `3042c600b`, clean tree. 4x P100 sm_60, `GGML_CUDA_ALLREDUCE=internal`,
clocks 1063 MHz / 150 W.

## 1. Flash-Next Q2, `-sm tensor`, 4 devices — still good

```
llama-server -m Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf \
  -ngl 99 -sm tensor -c 4096 --port 8087 -np 1
```

```
' Paris. Paris is the most populous city in France, with a population of 2.1 million people.
  It is also the most visited city in the world, with over 30 million tourists'
```

VRAM **13603 / 13633 / 13603 / 13603 MiB** — unchanged from `163517b9a`. No regression from the
central policy.

## 2. DS4, even `-ts 1,1,1,1` — the policy works exactly as intended

Warm-up does **not** complete, but this is now a clean stop rather than a corrupt write:

```
llama-server -m DeepSeek-V4-Flash-0731-UD-IQ1_S-00001-of-00003.gguf \
  -ngl 99 -sm tensor -c 8192 --port 8087 -ts 1,1,1,1 -fit off -fa on -ncmoe 40 -np 1
```

```
llama-model.cpp:810: cannot tensor-split blk.0.attn_output_a.weight:
  segment 0 has only 1 splittable units for 4 devices;
  use fewer devices or a different split mode
```

This is a big improvement. On `163517b9a` the same config died at
`ggml-backend.cpp:472 tensor write out of bounds` during weight loading, and it took me an
instrumented build to learn that the tensor was `blk.0.attn_output_a.weight` with `ne=[4096,8192,0,1]`.
Your policy names it at the source, first try, with the reason. Exactly the single trace you wanted.

### But the suggested remedy cannot apply here

`segment 0 has only **1** splittable unit`. So I tested two devices as well:

```
CUDA_VISIBLE_DEVICES=0,1 ... -ts 1,1
llama-model.cpp:810: cannot tensor-split blk.0.attn_output_a.weight:
  segment 0 has only 1 splittable units for 2 devices; use fewer devices or a different split mode
```

**One unit fails at any device count >= 2**, so "use fewer devices" bottoms out at one device,
i.e. not tensor split at all. For this tensor the only workable options are the ones you already
built for undersubscribed dense GQA — **mirror it** — or exclude it from the split.

That reads consistent with the architecture rather than a bug: DeepSeek-V4 is MLA with
`head_count_kv = 1`, so there is genuinely nothing per-head to divide. `attn_output_a` is the
grouped output projection over a shared latent, and the split-state already mirrors the
corresponding weights on exactly this reasoning —

```cpp
// DS4 q_a/kv are low-rank down-projections feeding per-row norms; column split would split
// the norm row, so mirror them
pattern_ds4_q_a_kv_weight -> GGML_BACKEND_SPLIT_AXIS_MIRRORED
```

So the mirrored path may simply need to extend to `attn_output_a`/`attn_output_b` for MLA.
Whether the rest of DS4 then splits usefully, I can't say without trying it — happy to test any
patch on 2 and 4 cards.

Worth noting the error text itself might be worth a tweak: when unit count is 1, "use fewer
devices" is unreachable advice. Something like "this tensor cannot be tensor-split at all;
it must be mirrored" would have saved me the second run.

## 3. Status summary

| check | `163517b9a` | `3042c600b` |
|---|---|---|
| Flash-Next Q2, 4 dev | coherent | **coherent**, VRAM identical |
| DS4 `-ts 1,1,1,1` | OOB write at load, tensor unidentified without instrumentation | **named at source**, one clear diagnostic |
| DS4 `-ts 1,1` (2 dev) | not run | same refusal — 1 unit for 2 devices |

Did not re-run the undersized Qwen3Next fixture, per your note.
