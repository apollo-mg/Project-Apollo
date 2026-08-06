# APEX i-mini (Puzzle-75B @ 2.94 bpw) does **not** fit on 2× P100 — and neither KV size nor split balance is the lever

`.73`, 2× Tesla P100-PCIE-16GB (sm_60), 16,269 MiB usable each = **31.78 GiB total**.
Model: `Nemotron-Labs-3-Puzzle-75B-A9B-APEX-i-mini.gguf`, 31.0 GB = **28.87 GiB**, 2.94 bpw.
Build: `~/llama_stock_ref/build_puzzle73` @ **`adeff9b82`** — upstream PR #25444 head (stock
llama.cpp + Puzzle support), CUDA arch 60. Date 2026-08-02.

**Result: no configuration loads.** Nine attempts across two axes, all OOM.

## Axis 1 — KV cache size and type (5 arms, `-sm layer -ts 1,1`)

| context | KV type | result |
|---|---|---|
| 8192 | f16 | OOM |
| 8192 | q8_0 | OOM |
| 4096 | q8_0 | OOM |
| 2048 | q8_0 | OOM |
| 2048 | q4_0 | OOM |

**KV configuration is not the lever.** A 4× context reduction and f16→q4_0 (an 8× KV shrink in
combination) produce byte-identical failures. The terminal error is allocating **140 MiB on
device 0** — device 0 is full of *weights*, so shrinking the cache cannot help. This is worth
stating because shrinking KV is the obvious first instinct and it is provably useless here.

## Axis 2 — split mode and balance (4 arms, all `-c 2048 -ctk/-ctv q8_0`)

| arm | failure |
|---|---|
| `auto` (llama.cpp's own proportional split) | allocating **142 MiB** on device 0 |
| `-sm layer -ts 1,1` | allocating **140 MiB** on device 0 |
| `-sm layer -ts 4,6` | allocating **17,636 MiB** on device 1 (card holds 16,269) |
| `-sm layer -ts 3,7` | allocating **21,299 MiB** on device 1 |
| `-sm row` | **rejected outright** — see below |

**Split balance is not the lever either.** Biasing layers off the full card makes it strictly
worse: at `4,6` device 1 is asked for 17.6 GiB and at `3,7` for 21.3 GiB, both beyond a 16.3 GiB
card. Back-solving from the `4,6` arm (17,636 MiB for 60% of layers) gives **total weights
≈ 29.4 GiB**, consistent with the 28.87 GiB file plus load overhead.

### Why an even split still fails — the compute buffer is not split

At `1,1` each card holds ~14.35 GiB of weights against 15.89 GiB usable, which looks like ~1.5 GiB
of headroom. But the **compute buffer is allocated whole on device 0**, and the log shows it
asking for **1,749 MiB** there. 14.35 GiB + 1.71 GiB ≈ 16.06 GiB > 15.89 GiB. The retry without
pipeline parallelism drops the request to 142 MiB and *still* fails, so device 0 has under
142 MiB free once weights and KV are placed.

So the budget is: **28.87 GiB weights + ~1.71 GiB compute buffer ≈ 30.6 GiB**, against 31.78 GiB
total — but the compute buffer lands entirely on one 15.89 GiB card, which is where it breaks.

## Neither alternative split mode is available — for two *different* reasons

This build offers `-sm {none,layer,row,tensor}`. Both non-layer modes are rejected immediately
(~0.2–0.5 s, before any allocation), and the reasons are unrelated:

**`-sm row` — a hardware/backend limit:**
```
llama_model_load: error loading model: device CUDA0 does not support split buffers
```
sm_60 has no split-buffer support in this build.

**`-sm tensor` — an *architecture* limit:**
```
common_fit_params: llama_params_fit is not implemented for SPLIT_MODE_T…
llama_model_load: error loading model:
    LLAMA_SPLIT_MODE_TENSOR not implemented for architecture 'nemotron_h_moe'
```
Identical at `-c 2048`, `4096` and `8192`.

**Tensor split is implemented per architecture, not generically.** That is precisely what
`ce3dce77b` ("llama : mirror DS4 q_a/kv down-projections in tensor split") did for
`deepseek4` — and why DS4 gets far enough to hit *runtime* asserts
(`DS4_TENSORSPLIT_POST_CE3DCE77B.md`) while Puzzle is refused at load. DS4 has a partial
implementation; `nemotron_h_moe` has none.

Practical consequence: for Puzzle on this fleet, **`-sm layer` is the only available mode**, so
the imbalance it causes on a heterogeneous NAS-derived model cannot be worked around by
switching modes. It can only be mitigated with `-ts`, which axis 2 shows makes things worse here.

## What would be needed

- **~1.8 GiB less** on device 0. Not reachable by KV or split tuning (both shown above).
- Candidates not tested here: the fork's turbo3/turbo4 KV (unavailable on this stock build),
  partial CPU offload via `-ncmoe` (defeats the purpose of the "fits in 32 GB" question),
  or a smaller quant than 2.94 bpw (none exists in the APEX repo).
- A third P100 would trivially solve it, but the question was specifically 2-card.

## Limits

- One build (`adeff9b82`, stock + PR #25444). **The turboquant fork was not tried** — it may fit
  where this does not, via turbo3 KV and a smaller compute buffer. That is the obvious follow-up
  and this receipt does **not** claim i-mini is unfittable in general, only on this build.
- `-ngl 99` throughout, i.e. full offload. Partial offload was not explored.
- The sm_60 FAST_FP16 carveout is deliberately **not** applied (preserved on branch
  `sm60-carveout-73`), to keep this build comparable to leg W3's `.194` binary.
- Load-only test. Nothing here says how i-mini would *perform* if it fit.

## Provenance

- `.73:~/imini_fit/` — `fit.log`, `server_c{8192,4096,2048}_*.log`
- `.73:~/imini_split/` — `split.log`, `server_{auto,row,layer_46,layer_37}.log`
- Scripts `scratchpad/imini_fit.sh`, `scratchpad/imini_split.sh`, `scratchpad/build73b.sh`
- Related: `../../Apollo Docs/Lab_Spec_Puzzle_APEX_Parallel.md` (Phase 3)
