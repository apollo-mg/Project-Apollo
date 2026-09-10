# `--split-mode tensor` prevents VBR artifact-store pool binding

**Date:** 2026-09-07 · **Node:** `.73`, 2× Tesla P100 (sm_60), CUDA 12.4
**Build:** buun-llama-cpp `c9c52d71` (`build_sm60_head`, binary 2026-09-06 20:00:30)
**Status:** RESULT. Supersedes the framing sent to buun on 2026-09-06 — see Corrections.
**Widened same day** by `RESULT_TENSOR_SPLIT_BREAKS_ALL_CACHING.md`: tensor split breaks
prompt-cache reuse for f16 and q8_0 as well, silently. VBR is the only codec that reports it.

## Finding

Under `--split-mode tensor`, the VBR artifact store discovers its runtime pools but binds
none of them, so prompt-cache capture is disabled and every request pays a full prefill:

```
VBR_ARTIFACT_CAPTURE topology unavailable reason=runtime_pool_binding_failed
  devices=2 resolved_split=2 topologies=1 runtime_pools=2 bindings=0 lanes=0 attention_children=1
automatic dynamic VBR host caching fallback=live_only
  reason=artifact_topology_unavailable store_status=unavailable store_failure=none; cache-ram disabled
```

Under `--split-mode layer` the same binary, same model, same two GPUs binds normally.

## Discriminator

Five arms, `Qwen3.5-4B-Q5_K_S.gguf`, identical flags apart from split mode and device
visibility. `-ngl 99 -c 32768 -np 1 -fit off -fa on --kv-unified -ctk vbr -ctv vbr
--vbr-floor t4 --vbr-vram 512M --cache-ram 4096`. Whole sweep ran in 19 s.

| arm | split mode | tensor-split | devices | result |
|---|---|---|---|---|
| A | tensor | automatic | 2 | `runtime_pools=2 bindings=0 lanes=0` — **fail** |
| B | tensor | `1,1` explicit | 2 | `runtime_pools=2 bindings=0 lanes=0` — **fail** |
| C | layer | automatic | 2 | `store ready … lanes=2` — **ready** |
| D | layer | `1,1` explicit | 2 | `store ready … lanes=2` — **ready** |
| E | layer | automatic | 1 (`CUDA_VISIBLE_DEVICES=0`) | `store ready … lanes=1` — **ready** |

All five arms reached `listening on`. Raw: `.73:~/artbind.log`, per-arm `~/ab_[A-E].log`.

**Split mode is the only variable that moves the outcome.** Device count does not (C is
multi-GPU and binds). Explicit `--tensor-split` does not (B still fails, D and C agree).

## Mechanism (read, not measured)

`tools/server/server-context.cpp:8129-8150`. `runtime_pool_binding_failed` is assigned as
the pessimistic default on entering the bind block, then each discovered pool is matched
against `cache_authority->live_device_domains`:

```cpp
const auto domain = std::find_if(
    cache_authority->live_device_domains.begin(),
    cache_authority->live_device_domains.end(),
    [&](const auto & binding) { return binding.device == pool.backend_device; });
if (domain == cache_authority->live_device_domains.end()) {
    capture_pool_bindings.clear();
```

`runtime_pools=2 bindings=0` means both lookups missed. buun's own comment from the August
fix names the likely reason — `src/llama-model.cpp` (in `2174ad63b`):

> Tensor parallelism exposes one meta device to the model loader. Its split callback,
> however, distributes rows across the physical devices recorded here…

So under `-sm tensor` `pool.backend_device` is plausibly the meta device while
`live_device_domains` is built from the physical `gpu_devices[i]`. Unverified — this is a
code reading, not an instrumented run.

## Relationship to the August fix

`2174ad63b "vbr: fix automatic multi-GPU prompt capture"` (2026-08-26) **is an ancestor of
`c9c52d71`** (`git merge-base --is-ancestor` confirms). That fix addressed an all-zero
`tensor_split` being rejected at `llama-cache-accounting.cpp:81` before pool discovery ran.

It is still working: the current failure reports `resolved_split=2`, i.e. the split
resolves. Discovery now succeeds too (`topologies=1`, `runtime_pools=2`). The failure has
moved one stage later, into the pool→domain binding.

Contemporary evidence that the store bound correctly after that fix, on this node:
`.73:~/cache_restore.log` (2026-08-26, build `2174ad6`) and `~/cache_restore2.log`
(2026-08-27) — `VBR_ARTIFACT_CAPTURE store ready`, cache speedups 20.06× (vbr) and 40.98×
(f16), identical output verified. Those runs used `--split-mode layer`.

## Consequence measured 2026-09-06 (27B, production config, `-sm tensor`)

Qwen3.8-27B, `-c 262144 -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto -sm tensor
--spec-type draft-mtp --draft-max 3 --kv-unified`. Identical prompt twice, one client:

```
task 50 | divergence (cached/incoming/lcp/reusable/rewind/append/cache_prompt)
        = (4565/4562/4562/4562/3/0/1)
task 50 | prompt eval time = 30038.85 ms /  4562 tokens ( 6.58 ms per token, 151.87 tokens per second)
```

The planner reports the whole prefix reusable and `append=0`; the executor still evaluates
all 4,562 tokens at cold rate. Client-side sweep, cold vs warm:

| prompt tokens | cold | warm | saving |
|---:|---:|---:|---:|
| 282 | 2.70 s | 2.58 s | 4.4% |
| 1,062 | 7.15 s | 7.18 s | −0.6% |
| 2,862 | 16.58 s | 16.58 s | 0.0% |
| 5,262 | 30.04 s | 30.05 s | 0.0% |

Linear with no fixed floor, which rules out VBR transcode cost and 256k slot allocation.
At ~25k tokens of Hermes system prompt this is ~180 s before the first token.

The same failure appears in `~/wake_proxy_server.log`, so it affects the node's normal
serving path, not only test rigs.

## Corrections to the 2026-09-06 report sent to buun

1. **"Suspected multi-GPU-specific" — FALSIFIED.** Arm C is two GPUs and binds. The
   variable is split mode.
2. **"`runtime_pools=`" (reported empty) — WRONG, an artifact of my own truncation.** The
   greps that produced it ran through `cut -c1-185`, which cut the line mid-field and
   dropped `bindings=` and `lanes=` entirely. Actual value is `runtime_pools=2 bindings=0`.
   Reported as "pools never came up" when the truth is "pools came up and none bound" —
   a different subsystem.

Method note: this is the second time in two weeks a conclusion was shaped by a truncated
or stale read (cf. `kv-tensor-split/RESULT_TURBO_COLLAPSE_IS_BUUN_SIDE.md`). Diagnostic
lines get read whole or not quoted.

## Distinct from

- **`prompt-cache-prefix/FINDING.md`** (2026-08-14) — a *harness*-layer, code-reading
  finding about `apollo_server.ts` invalidating its own cache prefix via
  `searchMemory(userText)`. Different layer, different repo, still unmeasured. Nothing here
  bears on it.
- **buun issue #121** — cross-agent digest invalidation, where a guard correctly fires.
  Zero guard rejections appear anywhere in these logs: no `currency_changed`, no
  `unsupported_layout`. Nothing was captured to invalidate.

## Limits

- One node, sm_60, one fork. Not tested on CUDA ≥ sm_70 or RDNA. The mechanism reading
  suggests it is architecture-independent, but that is not measured.
- The meta-device explanation is read from source, not confirmed by instrumenting
  `pool.backend_device`.
- Arms A–E confirm binding, not cache reuse. See the A/B in this directory for whether
  `-sm layer` restores measured reuse rather than only the log line.
- Originally surfaced by Hermes Agent running against this server; it designed the
  repeat-probe and caught the `append=0` accounting mismatch.
