Ran your `ce3dce77b` (mirror DS4 q_a/kv down-projections in tensor split) against DS4-Flash on the quad-P100 box. **The fix works — that wall is gone.** The `handle_per_row` /
`GGML_ASSERT(src_ss[0].axis != GGML_BACKEND_SPLIT_AXIS_0)` abort I hit before doesn't reproduce.

Tensor-split still can't load DS4, but it now fails **later and for different reasons**, and there are two distinct ones depending on the split ratio.

Setup: 4× Tesla P100-PCIE-16GB (sm_60), build `331981025`, DeepSeek-V4-Flash-0731-UD-IQ1_S (82.5 GB), `-c 8192 -ngl 99 -fit off -fa on`.

| `-sm` | `-ncmoe` | `-ts` | result |
|---|---|---|---|
| layer | 40 | 3,4,4,1 | **loads, 4.74 t/s** (control — healthy) |
| tensor | 40 | 3,4,4,1 | `GGML_ASSERT(split_state.ne[j] % div == 0)` — `ggml-backend-meta.cpp:1038` |
| tensor | 30 | 3,4,4,1 | same, `:1038` |
| tensor | 20 | 3,4,4,1 | OOM — `allocating 16552.36 MiB on device 2` (16,269 MiB card) |
| tensor | 40 | **1,1,1,1** | `GGML_ASSERT(split_states_equal(src_ss[0], src_ss[2]))` — **`:730`** |
| tensor | 40 | **(omitted)** | same, **`:730`** |

I tested the even ratios specifically to check whether the `:1038` assert was ratio-dependent, since it's a proportionality check —

```cpp
// ggml-backend-meta.cpp:1037
const int64_t div = tensor->src[i]->ne[src_ss[i].axis] * split_state.nr[0];
GGML_ASSERT(split_state.ne[j] % div == 0);
```

— and `3,4,4,1` makes exact divisibility hard to satisfy. It is ratio-dependent, but **even ratios aren't a workaround**: they just get further and hit `:730` instead, which is in `handle_set_rows`:

```cpp
// ggml-backend-meta.cpp:727-731
auto handle_set_rows = [&](const std::vector<...> & src_ss) {
    GGML_ASSERT(src_ss[0].axis != GGML_BACKEND_SPLIT_AXIS_1);
    GGML_ASSERT(src_ss[1].axis == GGML_BACKEND_SPLIT_AXIS_MIRRORED);
    GGML_ASSERT(split_states_equal(src_ss[0], src_ss[2]));   // <-- fires
    return src_ss[0];
};
```

So DS4's KV-cache `SET_ROWS` presents `src[0]` and `src[2]` with different split states. That one looks like the more fundamental blocker — the `:1038` proportionality assert is only reachable because the uneven ratio trips first.

The `-ncmoe 20` OOM is just capacity (283 MiB over a 16 GB card), not a bug.

Happy to instrument either assert the same way as last time — a `fprintf`/`fflush` diagnostic printing the op, tensor name, `ne[]` and the two split states before the abort — if that'd be useful. That's what localised the last one to `attn_q_a`/`attn_kv`, and I have the box free. Note the async logger won't work for this: `GGML_LOG_ERROR` dies unflushed before `GGML_ABORT`, so it has to be `fprintf(stderr)` + `fflush`.

Unrelated but possibly of interest since you're working this model: on the same box, `--numa distribute` is worth **+22.7%** on DS4 decode (4.58 → 5.62 t/s, 4 measured draws each, spreads <1%, caches dropped before every arm). With `-ncmoe 40` the experts are CPU-resident and GPU utilisation sits at 6.5%, so default first-touch placement across two sockets was leaving a fifth of the throughput on the table.
