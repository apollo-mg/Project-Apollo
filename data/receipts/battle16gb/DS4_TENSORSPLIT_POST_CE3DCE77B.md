# `ce3dce77b` fixed the DS4 tensor-split assert; two further walls sit behind it

`.194`, 4× Tesla P100-PCIE-16GB (sm_60), **1063 MHz / 150 W**. DS4-Flash UD-IQ1_S 82.5 GB,
build `331981025` (contains `ce3dce77b llama : mirror DS4 q_a/kv down-projections in tensor
split`). `-c 8192 -ngl 99 -fit off -fa on`. Date 2026-08-02.

## Result

| `-sm` | `-ncmoe` | `-ts` | outcome |
|---|---|---|---|
| layer | 40 | 3,4,4,1 | **loads, 4.74 t/s**, GPU util 6.5% mean / 8% max (control) |
| tensor | 40 | 3,4,4,1 | `GGML_ASSERT(split_state.ne[j] % div == 0)` — `ggml-backend-meta.cpp:1038` |
| tensor | 30 | 3,4,4,1 | same, `:1038` |
| tensor | 20 | 3,4,4,1 | OOM — `allocating 16552.36 MiB on device 2` (16,269 MiB card) |
| tensor | 40 | 1,1,1,1 | `GGML_ASSERT(split_states_equal(src_ss[0], src_ss[2]))` — `:730` |
| tensor | 40 | *(omitted)* | same, `:730` |

**Jabba's fix is confirmed.** The previous failure — `handle_per_row` rejecting an axis-0-split
source into `RMS_NORM`, traced to `attn_q_a`/`attn_kv` — does not reproduce. The wall moved.

## The ratio hypothesis, and its falsification

`:1038` is a proportionality check:

```cpp
const int64_t div = tensor->src[i]->ne[src_ss[i].axis] * split_state.nr[0];
GGML_ASSERT(split_state.ne[j] % div == 0);
```

The destination axis must divide across the same buffer ratio as the source, exactly. Every DS4
run on this fleet has used `-ts 3,4,4,1` (chosen for the cards' differing free VRAM), and uneven
ratios make that much harder to satisfy. **Predicted:** even ratios would load.

**Falsified.** `1,1,1,1` and the default split both fail — but at a *different, earlier* assert,
`:730` in `handle_set_rows`:

```cpp
GGML_ASSERT(src_ss[0].axis != GGML_BACKEND_SPLIT_AXIS_1);
GGML_ASSERT(src_ss[1].axis == GGML_BACKEND_SPLIT_AXIS_MIRRORED);
GGML_ASSERT(split_states_equal(src_ss[0], src_ss[2]));   // fires
```

So the prediction was half right in a way that only testing could distinguish: the ratio **is**
what selects `:1038`, but it is not the blocker. DS4's KV-cache `SET_ROWS` presents `src[0]` and
`src[2]` with unequal split states regardless of ratio, and that is the deeper constraint. Had
the even-ratio arm not been run, the natural (wrong) write-up would have been "tensor-split
needs even ratios."

The `-ncmoe 20` OOM is capacity, not a defect — 283 MiB over a 16 GB card.

## What this closes

`-ncmoe` **cannot** currently drop below 40 on this fleet by any route:

- layer-split at 30 OOMs (whole layers land on one device; one DS4 layer's expert tensors exceed
  16 GB)
- tensor-split, which would shard those tensors, cannot build the graph at any ratio

So the CPU-resident-expert regime — and the 6.5% GPU utilisation that comes with it — is
structural for DS4 on 4×16 GB, not a tuning failure. **The throughput lever that did work was
`--numa distribute` (+22.7%), which is a CPU-side memory-placement fix**, consistent with the
bottleneck being where the experts live rather than how the GPUs are fed. See
`DS4_NUMA_DISTRIBUTE.md`.

## Limits

- Load-only test: arms that fail never generate, so nothing here says whether tensor-split would
  be *faster* if it loaded.
- Two even-ratio configurations tested (`1,1,1,1`, default). Ratios that are even but unequal
  (e.g. `2,2,2,2` vs `4,4,4,4`, or `2,4,4,2`) were not tried; `:1038` might be satisfiable by
  some other ratio that still reaches `:730`.
- No diagnostic patch was applied, so neither assert is attributed to a *named tensor*. The
  previous wall needed exactly that to become actionable.
- One model, one build, one machine.

## Provenance

- `.194:~/ts_ratio/` — `ts_ratio.log`, `server_{even_1111,no_ts}.log`
- `.194:~/ds4_tsspeed/` — `tsspeed.log`, `server_{layer_n40,tensor_n40,tensor_n30,tensor_n20}.log`
- Script `scratchpad/ts_ratio.sh`, `scratchpad/ds4_tensorsplit_speed.sh`
- Pastable drafted for Jabba: `JABBA_TS_FOLLOWUP_PASTABLE.md`
