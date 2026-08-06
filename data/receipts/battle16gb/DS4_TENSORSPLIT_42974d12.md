# DS4 tensor-split on 4×P100: Jabba's fix clears the load gate, moves the memory wall one rung, and exposes a second assert at warmup decode

`.194`, 4× Tesla P100-PCIE-16GB (sm_60, 16,269 MiB each), 2× Xeon E5-2650 v3, 60 GiB
DDR4-2133 ECC, **1063 MHz / 150 W** standing config (405 MHz / 0 MiB at launch, verified).
Model `unsloth/DeepSeek-V4-Flash-0731-GGUF` **UD-IQ1_S**, 82.5 GB.
Build: `giveen/feature/turboquant-kv-cache-rebase` @ **`42974d12`** "llama : support
DeepSeek-V4 tensor split", `CMAKE_CUDA_ARCHITECTURES=60`. Date 2026-08-01.
Predictions logged before the run: `PREDICTIONS_ds4_tensorsplit.md`.
Baseline: `DS4_FLASH_P100_LOAD.md` (`-sm layer -ts 3,4,4,1 -fit off -fa on -ncmoe 40`,
2.16 t/s). Prior bug report: `TOM_DS4_SPLITMODE_PASTABLE.md`.

**Note on the commit.** Jabba's Discord message named `04ccc10da`, which does not resolve as
a fetchable ref. The commit matching his description (+7/−3, DS4 QKV patterns) is
`42974d12`. Everything here is that commit.

## Headline

Three separate results, and they must not be collapsed into one verdict:

1. **The load gate is cleared.** `GGML_ASSERT(!suffix_fallback.empty())` at
   `llama-model.cpp:416` is gone. DS4 now allocates all weight buffers under `-sm tensor`.
2. **The memory wall moved one rung** — `-ncmoe 40 → 30`. Measured, weight-phase, apples
   to apples (see below).
3. **A second assert now fires at warmup decode**, before any token is produced:
   `ggml-backend-meta.cpp:541`, `GGML_ASSERT(src_ss[0].axis != GGML_BACKEND_SPLIT_AXIS_0)`
   in `handle_per_row`. This is the "secondary meta-split assertion" Jabba predicted.

**No token was ever generated under `-sm tensor`. Numerical correctness of the split is
completely untested.** Clearing an assert is not evidence the shards recombine correctly —
turbo3 loaded and ran fine under the wave64 ballot bug while emitting gzip 0.175–0.347.

## The wall moved — weight-phase, verified

`-ncmoe 30` under layer-split died at `alloc_tensor_range` (the **weight** path, not graph
allocation). Under tensor-split the same rung allocates and reaches warmup decode. Both
sides of the comparison are the same allocation phase, confirmed by log inspection rather
than assumed.

| `-ncmoe` | layer-split largest single-device request | tensor-split | outcome |
|---|---|---|---|
| 40 | fits | fits | both load |
| **30** | **20,587 MiB → OOM** (`alloc_tensor_range`, dev2) | **fits** (≤16,269) | **tensor-split loads** |
| 20 | 28,251 MiB → OOM (`alloc_tensor_range`, dev2) | 16,412 MiB → OOM (`alloc_tensor_range`, dev2) | still capacity-bound |

**The reduction is ~1.72×, not 4×.** At `-ncmoe 20` the largest single-device weight request
falls 28,251 → 16,412 MiB. Sharding across four cards would predict ~4×. So tensor-split is
splitting *some* tensors and not others — consistent with the split patterns covering
attention while routed-expert tensors remain whole. That is enough to clear one `-ncmoe`
rung and no more; at 20 it misses by 143 MiB against a 16,269 MiB card.

This **retires the open question** in `DS4_FLASH_P100_LOAD.md`, which recorded the 20 GB
ceiling as UNPROVEN because no alternative split mode would load. A working tensor-split
now exists at the allocation level: the ceiling is real but it is *not* indivisible — it
shards partially.

## `-fit off` is cosmetic here

Jabba's suggested line omits `-fit off` and emits
`llama_params_fit is not implemented for SPLIT_MODE_TENSOR, abort`. That is a **warning**;
the run continues, loads, and hits the same decode assert. All five arms failed identically.

**Correction to an earlier reading of mine:** I initially reported Jabba's line as failing
at 1.4 s in the fitter, distinct from the `-fit off` arms. Wrong. `ggml_abort` prints
without a timestamp, and I dated the assert by the timestamped line preceding it. The ~3 min
per arm is gdb generating the backtrace, not model loading.

## The failing call path

```
common_init_from_params → llama_decode → llama_context::decode
  → process_ubatch → ggml_backend_sched_alloc_graph → ggml_gallocr_alloc_graph
  → ggml_backend_meta_buffer_init_tensor → ggml_backend_meta_get_split_state
  → handle_per_row → GGML_ASSERT(src_ss[0].axis != GGML_BACKEND_SPLIT_AXIS_0)
```

Frame `common_init_from_params` places this at the **warmup decode**, which only runs after
the model is fully loaded — independent confirmation that weight allocation succeeded.

## Root cause — CONFIRMED by instrumentation and source

An instrumented build (local diagnostic patch printing the op and its srcs from
`handle_per_row`) names it exactly:

```
PERROW_DIAG2: op=RMS_NORM dst='norm-0' ne=[1024,2,1,1]
PERROW_DIAG2:   src[0]='qr-0' axis=0 ne=[1024,2]
```

`RMS_NORM` at layer 0, consuming `qr` — split along axis 0 — with `ne[0]=1024`, the DS4
`q_lora_rank`. The graph builder `src/models/deepseek4.cpp:831-834`:

```cpp
ggml_tensor * qr = build_lora_mm(layer.wq_a, cur);   // attn_q_a  → qr, ne[0] = q_lora_rank
cb(qr, "qr", il);
qr = build_norm(qr, layer.attn_q_a_norm, nullptr, LLM_NORM_RMS, il);   // ← asserts here
ggml_tensor * q = build_lora_mm(layer.wq_b, qr);     // attn_q_b
```

`layer.wq_a` is `LLM_TENSOR_ATTN_Q_A` = `attn_q_a.weight` (`deepseek4.cpp:92`), which
Jabba's `pattern_ds4_qkv_weight` matches and assigns `GGML_BACKEND_SPLIT_AXIS_1`
(column-parallel). Column-splitting a weight splits its output activation along ne[0], and
the very next op RMS-normalises across ne[0]. `handle_per_row` correctly refuses.

**This is two bugs, not one.** The kv path has identical structure
(`deepseek4.cpp:856-857`):

```cpp
ggml_tensor * kv = build_lora_mm(layer.wkv, cur);    // attn_kv (LLM_TENSOR_ATTN_KV, :95)
kv = build_norm(kv, layer.attn_kv_norm, nullptr, LLM_NORM_RMS, il);
```

The same regex matches `attn_kv.weight`. Fixing only `q_a` moves the assert to the kv path.

**Fix direction:** the low-rank *down*-projections `attn_q_a` and `attn_kv` are followed
immediately by per-row norms and must not be column-split — standard MLA tensor parallelism
replicates (MIRRORS) the down-projection and its norm, and splits only the *up*-projections
`attn_q_b` / `attn_kv_b` column-parallel. Jabba's regex `attn_(q_[ab]|kv)\.weight` covers
`q_a`, `q_b` and `kv` in one pattern; `q_a` and `kv` need separating out.

## Earlier hypothesis (recorded — it was correct)

`handle_per_row` requires that src0 is not split along axis 0: a per-row op cannot complete
locally if a row's features are spread across devices.

Jabba's `pattern_ds4_qkv_weight` is `blk\.\d*\.attn_(q_[ab]|kv)\.weight`, assigned
`GGML_BACKEND_SPLIT_AXIS_1` (column-parallel). That regex matches **`attn_q_a`** and
**`attn_kv`** — the low-rank *down*-projections. DS4 is MLA-style and defines
(`llama-arch.cpp`):

```
blk.%d.attn_q_a  →  blk.%d.attn_q_a_norm  →  blk.%d.attn_q_b
blk.%d.attn_kv   →  blk.%d.attn_kv_a_norm →  blk.%d.attn_kv_b
```

Column-splitting a down-projection leaves its output activation split along the feature
axis, and the very next op is an RMS norm — a per-row op. Standard MLA tensor parallelism
replicates the down-projection and its norm, and splits only the *up*-projections
(`q_b`, `kv_b`) column-parallel.

Secondary concern, lower confidence: the widened `pattern_attn_out_weight`
(`attn_output(_[ab])?\.weight`) assigns **both** halves of the factored output projection
`AXIS_0`. For a factored projection `W = B·A` the conventional split is A column-parallel,
B row-parallel. Both at axis 0 is suspect, but it should surface as a partial-sum problem
rather than as this assert.

**Status: confirmed** — see the instrumented output above. The MLA reasoning predicted the
result before the diagnostic ran; the only thing it missed was that the kv path is a second
instance of the same defect.

Note on the instrumentation itself: round 1 used `GGML_LOG_ERROR` and printed **nothing**,
even though the assert on the identical condition fired. llama.cpp's common logger is
asynchronous, so the buffered line dies with the process on `GGML_ABORT`. Round 2 used
`fprintf(stderr)` + `fflush`. Worth remembering — a logger that silently drops the last
message before an abort is exactly the wrong logger for diagnosing an abort.

## Regression check on the working path — clean tree, no diagnostic patch

The patch widens regexes, and a widened regex can capture tensors it was never meant to. So
the question is not only "does `-sm tensor` work" but "did `-sm layer` **regress**". Run on a
clean `42974d12` (diagnostic patch reverted, rebuilt, `version: 10245 (42974d12)`).

| model | config | result |
|---|---|---|
| DS4-Flash IQ1_S | `-sm layer -ts 3,4,4,1 -fit off -fa on -ncmoe 40` | **2.20 t/s**, gzip 0.4649, CJK 0, vram `[3491, 2641, 4507, 4529]` — **no regression** (baseline 2.16 t/s, gzip 0.469–0.567) |
| Puzzle-75B IQ4-XL | `-c 32768 -sm layer -ts 1,1,1,1 -fit off -fa on` | fails to load — **pre-existing, not this patch** |

**DS4 layer-split is unharmed.** 2.20 vs 2.16 t/s is instrument noise at K=1, and VRAM
placement is identical to the baseline run.

**The Puzzle failure is not a regression, and my script mislabelled it as one.** The error is

```
key nemotron_h_moe.expert_used_count has wrong type arr but expected type u32
```

— GGUF hparam parsing, which happens long before any split-state code, and which
`42974d12` (+7/−3, regexes and `llm_arch_supports_sm_tensor` only) cannot touch. Two
independent confirmations:

1. The Puzzle ladder was never run on this fork. `PUZZLE_LADDER_FA_ON.md` records
   `llama_stock/build_puzzle` @ `73a55486c` (build **9937**) — stock llama.cpp.
2. The older turboquant build `558c6b78e` (build **9919**), which predates Jabba's patch
   entirely, **fails identically**. Pre-existing fork limitation.

The turboquant fork's base is older than the upstream commit that taught Nemotron-H MoE to
read `expert_used_count` as a per-layer array. Puzzle is a NAS-derived heterogeneous
architecture, so per-layer expert counts are exactly what it needs. Worth re-testing on
PR #244 (build 10240), whose base is far newer.

**Method note:** my sanity script hardcoded "REGRESSION" on any load failure. A load failure
is not evidence of a regression unless the same binary lineage previously loaded that model —
which was never established for Puzzle on this fork. Verify the baseline exists before
labelling its absence a regression.

## Prediction scoring

| id | claim | conf | outcome |
|---|---|---|---|
| P-T1 | past the `suffix_fallback` assert at `-ncmoe 40` | 0.75 | **CONFIRMED** |
| P-T2 | generates coherently, gzip 0.42–0.60 | 0.55 | **UNRESOLVED** — no token ever produced |
| P-T3 | `-ncmoe 30` loads under tensor-split | **0.35** | **CONFIRMED** |
| P-T4 | decode ≥ 2.16 t/s | 0.45 | **UNTESTABLE** — never decoded |
| P-T5 | a new, different assert appears | 0.40 | **CONFIRMED** |

P-T3 is the one worth dwelling on. I put it at 0.35 reasoning that `-ncmoe` offloads MoE
expert tensors while Jabba's patch only adds *attention* patterns, so experts would stay
whole and the wall would be untouched. The wall moved anyway — but the 1.72× (not 4×)
reduction says the underlying reasoning was half right: experts do appear to stay whole,
and the gain came from attention tensors alone being enough to clear one rung.

P-T2 is scored UNRESOLVED, not falsified. The run never generated, so nothing was learned
about output quality either way. Recording it as falsified would imply tensor-split produces
bad output, which was not measured.

## Limits

- **K=1 per configuration.** Load-time asserts are deterministic (the prior campaign saw the
  same assert at four offload levels), but nothing here is a throughput or quality result.
- No token was generated under `-sm tensor` at any setting. Decode speed vs the 2.16 t/s
  layer-split baseline is unknown.
- The 1.72× figure comes from a single `-ncmoe 20` comparison of the largest failing
  request. It is a lower bound on sharding effect at one rung, not a measured split ratio.
- Values between `-ncmoe` 21 and 29 were not tested; the tensor-split floor is somewhere in
  that range, not necessarily 30.
- Root cause is inferred from source reading; the instrumented run had not completed when
  this section was written.

## Provenance

- `.194:~/ds4_tsplit/` (5 arms), `~/ds4_diag/` (instrumented), script `~/ds4_tensorsplit.sh`
- Baseline logs: `~/ds4_sweep/`, `~/ds4_ts/` — `server_n30_ts_bal.log:15-16`,
  `server_n20_ts_hard.log:15-16` carry the layer-split OOM lines quoted above
- Build `~/llama_tq_ds4/build_ds4` @ `42974d12`; sm_60 FAST_FP16 carve-out verified present
- Diagnostic patch to `ggml-backend-meta.cpp` `handle_per_row` is **local and
  diagnostic-only** — not a fix, not for upstreaming
