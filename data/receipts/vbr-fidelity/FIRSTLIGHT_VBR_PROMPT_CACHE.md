# `--vbr-prompt-cache` on sm_60 — first-light report

**2026-08-26.** buun-llama-cpp **`2714303`** (fresh build, `build_sm60_head`, CUDA arch 60,
Release). Host `.73`, 2× Tesla P100 sm_60, 1063 MHz / 150 W.

Testing the prompt-cache work landed in `34941d33b` ("vbr: complete automatic prompt cache
lifecycle", 9865 insertions, new `server-vbr-artifact-store.cpp` /
`server-vbr-capture-readiness.cpp`).

## Confirmed: the blanket disable is gone

The old warning — *"prompt cache state storage is not supported by dynamic VBR (KV tiers
change at runtime), it will be disabled"* — no longer exists in the tree. Three disables
remain and still fire: `cache_reuse`, slot save/restore, SWA context checkpoints.

## But the feature does not activate here, on any config tried

**Automatic path** (`-ct vbr --cache-ram 4096`, no explicit flag) — silently degrades:

```
W load_model: automatic dynamic VBR host caching fallback=live_only
  reason=artifact_topology_unavailable store_status=unavailable store_failure=none;
  cache-ram disabled
```

**Explicit path** (`--vbr-prompt-cache`) — hard startup failure, which reads as intended
("an explicit request remains a strict startup contract"):

```
E load_model: --vbr-prompt-cache is unavailable reason=artifact_topology_unavailable
  store_status=unavailable store_failure=none
E llama_server: exiting due to model loading error
```

## What we ruled out

| varied | tried | result |
|---|---|---|
| architecture | `Qwen3.5-4B-Q5_K_S` (hybrid, 8 of 32 layers attention) | unavailable |
| architecture | `Llama-3.2-3B-BF16` (dense, 28/28 attention) | unavailable |
| KV budget | `--vbr-vram 96M` (over-subscribed: *"budget 96.00 MiB exceeded … projected 116.00 MiB at 256 cells"*) | unavailable |
| KV budget | `--vbr-vram 2048M` + `--vbr-anchor-cache-mib 256` | unavailable |

So it is neither architecture nor budget.

## Traced to the gate

`server-context.cpp:7623` — `store_failure=none` because the store constructor is never
reached:

```cpp
if (params_base.vbr_prompt_cache && !vbr_artifact_store) {
    if (!capture_manifest_enabled) {
        vbr_prompt_cache_support = ...::artifact_topology_unavailable;
```

and `capture_manifest_enabled` (`server-context.cpp:7362`):

```cpp
capture_manifest_enabled =
    !capture_pool_bindings.empty() &&
    !capture_lanes.empty() &&
    capture_pool_bindings.size() == capture_runtime_pools.size();
```

One of those three is false on this host. We have not determined which — that needs either a
debug build or a one-line diagnostic printing the three counts, which would make this
self-diagnosing for anyone else who hits it.

**Question for buun:** is capture-pool/lane binding expected to work on sm_60 / multi-GPU
`-sm layer`, or does it depend on something the Pascal path does not provide? Worth knowing
whether this is a Pascal gap or a missing precondition we simply have not supplied.

## Unrelated but directly useful to us

```
W vbr_load_degrade_order: no measured VBR degrade order for this arch/n_layer — using the
  generic cross-model order (a measured per-model order is better; set VBR_DEGRADE_ORDER=<file>)
```

**That file is exactly what our layer-pricing bands produce.** We now have measured orders for
Qwen3.8-27B (16 KV layers, 3 transitions), Qwen3.5-4B (8 layers, Q5_K_S and BF16), and
Llama-3.2-3B (28 dense layers) — see `data/receipts/layer-pricing/`. Caveat from those runs:
the ranking is **not** transition-invariant on the 27B (t8 vs t2 ρ=+0.247, n.s.) and the
terminal-V rule that held in `qwen35` **inverted** on Llama, so a per-model order should be
generated at the transition it will actually be used at.
