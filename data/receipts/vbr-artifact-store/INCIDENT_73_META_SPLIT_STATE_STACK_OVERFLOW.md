# Incident -- .73 llama-server died by stack overflow in `ggml_backend_meta_get_split_state` (buun `0b2789f23`)

**2026-09-26 08:59:05 EDT.** The daily driver crashed on `.73`, triggered by the cross-model replay
(`loop-logits/PREREG_CROSS_MODEL.md`). It was restarted through the wake proxy at about 09:05 (new PID 2002403).
Nothing was lost except the in-flight probe.

## What ran

- **Server:** `.73`, buun `0b2789f23` (`~/buun-resume/build_sm60_resume`), Qwen3.8-27B Q6_K + mmproj.
  - `-ngl 99 -c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -np 4`.
  - 2x P100 tensor split through the meta backend ("internal AllReduce init failed ... falling back to meta-backend
    butterfly").
  - Server started 08:55:46 by the proxy.
- **Requests,** all `/completion`, `cache_prompt: false`, `n_predict 1`, `n_probs 20`, sent sequentially:
  1. 8,084 tokens -> slot 0: OK.
  2. 8,597 tokens -> slot 0 (LCP 0.94): OK, 57 s.
  3. **11,003 tokens -> slot 1** (fresh, chosen by LRU): the process died while processing the ubatch after
     6,144/11,003. By then the unified KV cache held about 8.6k cells of slot 0 plus 6-8k of slot 1.

## Evidence (`raw_meta_stack_overflow/`)

- **Kernel log:** `llama-server[1809477]: segfault at 7ffe99886198 ip 00007da8458dcc5c sp 00007ffe99886198 error 6 in
  libggml-base.so.0.24.0`. The fault address equals the stack pointer and error 6 is a write fault, so this is a
  **stack overflow**. `server_log_crash_excerpt.txt` ends mid-prefill with no error line, as expected for a
  SIGSEGV.
- **Core** (systemd-coredump, present on `.73`): the crashing thread has **584 frames**.
  - About 565 of them alternate between `ggml_backend_meta_get_split_state(stc&, const ggml_tensor*, bool)` and its
    `{lambda()#1}`, about 282 levels deep.
  - Below them (`core_bt_outer.txt`): `ggml_backend_meta_buffer_init_tensor_impl` <- `ggml_gallocr_alloc_graph`
    <- `ggml_backend_sched_alloc_graph` <- `llama_context::process_ubatch` <- `llama_context::decode` <-
    `llama_decode` <- `server_context_impl::update_slots`.
  - 8 MB / 584 frames ~= **14 KB of stack per frame**.

## Mechanism (from the source at `0b2789f23`, `ggml/src/ggml-backend-meta.cpp`) -- hypothesis, not verified

- `ggml_backend_meta_get_split_state` computes a node's split state by recursing into `tensor->src[i]` (l.~951). The
  result is memoized in `buf_ctx->split_state_cache`, keyed by (tensor, assume_sync).
- **The cache is validated by `memcmp` of the whole tensor struct. On any mismatch it is cleared entirely**
  (l.1209-1212: `if (... memcmp(...) != 0) { buf_ctx->split_state_cache.clear(); ... }`).
- If that clear happens while initializing a tensor deep in the graph, the next resolution re-walks that tensor's
  whole dependency chain with nothing memoized. Down the residual stream, that is about 64 layers x 4-5 ops
  ~= 280 levels, which matches the ~282 levels in the core. At ~14 KB per level, that exceeds the 8 MB main-thread
  stack.
- **Why only sometimes (unverified):** normally tensors are initialized in graph order, and a mismatch early in the
  graph (layer 0) refills the cache incrementally, so depth stays shallow. A crash needs the first mismatch to land
  on a *late* layer. A per-layer change that only affects some layers would do that, for example a dynamic VBR tier
  change on later layers' KV views as context grows. Consistent with the crash arriving mid-prefill after the
  unified cache passed about 14-15k cells, but not shown.

## For buun (suggested; his call)

- Erase only the stale key instead of `clear()`ing the whole cache, or resolve splits iteratively in topological
  order, so depth is bounded regardless of cache state.
- Reduce the per-level stack footprint (the ~14 KB frames suggest large `ggml_backend_meta_split_state` values held
  on the stack per level).

## Repro status

- Not reproduced yet. The request sequence above is recorded, and the same traces are in
  `loop-logits/raw/full_*` + `cross_model.py`.
- A repro needs the 2-GPU tensor split; the 9070 is single-GPU, so it cannot be tested there.
- **After the mitigation (512 MiB stack), the cross-model re-run completed the same 11,003-token probe.** That is
  *consistent* with the stack-overflow diagnosis, **not confirmation**. Slot state differed: a fresh load with
  warm-on-load, and a different request history, so the unmemoized walk may simply not have been triggered.

## Mitigation for the daily driver (APPLIED 2026-09-26 ~09:45, approved by Mark)

- The proxy's start command now begins `ulimit -s 524288;`, a 512 MiB stack. Verified on the live process:
  `Max stack size 536870912`. This avoids the overflow without fixing the recursion (see CHANGELOG).

## Also found

- The proxy **truncated `~/wake_proxy_server.log` on every relaunch**. The crashed server's log survived only
  because it had been tailed before the restart. **Fixed:** the start command now moves the old log to
  `~/wake_proxy_server.log.prev` first (verified).
