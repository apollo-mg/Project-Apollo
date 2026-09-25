# Incident -- at `-np 1`, a request that reuses a slot AFTER its idle VBR capture published aborts llama-server (`ggml-backend-meta.cpp:1783 GGML_ASSERT(size % row_stride == 0)`)

**2026-09-24 20:11-20:40, `.73`** (2x P100, sm_60), buun `08826ad6e` (`build_sm60_0920`), the **daily-driver config
at `-np 1`**: `Qwen3.8-27B-Q6_K` + mmproj, `-c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -np 1 -fit off
-sm tensor -fa on --spec-type draft-mtp --draft-max 3 --kv-unified`, default `--cache-ram`. Found while building the
wake proxy's pre-warm (`split-prefill-73/`). Logs: `raw_np1_idle_abort/*.log.gz` (home paths redacted).

This is the same assert family as `INCIDENT_73_NP4_TENSOR_CAPTURE_ABORT.md`, whose assert text was not recoverable.
**Here the text is captured, and the trigger is at `-np 1`.**

## The abort

```
ggml-backend-meta.cpp:1783: GGML_ASSERT(size % row_stride == 0) failed
#6  ggml_backend_meta_buffer_get_tensor
#7  chain_io_writer::write_tensor
#8  llama_memory_recurrent::state_write_data
#9  llama_memory_recurrent::state_write
#10 recurrent_companion_capture
#11 vbr_transfer_explicit_manifest
#12 server_vbr_artifact_store::transfer_host_payload
#13 server_context_impl::ensure_vbr_replacement_recovery
#14 server_context_impl::try_automatic_vbr_restore
#15 server_context_impl::launch_slot_with_task
```

The NP4 incident reached the same capture through `publish_idle_vbr_batch`. Here it goes through
`try_automatic_vbr_restore -> ensure_vbr_replacement_recovery`.

## Sequence (V5 log)

```
slot release: n_tokens = 9237                                      # turn 1 done
srv publish_idle: VBR_IDLE_CAPTURE manifests=1 published=1 ... union_cells=9210 duration_ms=4029   # ~4 s later
slot cache_plan_s: selected slot by LCP similarity, f_sim_best = 0.998                              # turn 2, 26 s later
ggml-backend-meta.cpp:1783: GGML_ASSERT(size % row_stride == 0) failed
```

## Repro matrix (fresh server each; ~9.2k-token head: 30k chars of system text + 6 tool schemas)

| variant | request 1 | wait before request 2 | request 2 | server |
|---|---|---:|---|---|
| 20:11 (proxy auto-warm) | raw `/completion` of the head, `n_predict 1` | ~5-60 s | chat extending the head | **aborted** |
| V1 | same, `n_predict 1` | 0 | chat extending the head | alive, reused 9,197 |
| V2 | same, `n_predict 1` | 30 s | same | **aborted** |
| V3 | same, `n_predict 0` | 0 | same | alive, reused 9,197 |
| V4 | same, `n_predict 0` | 30 s | same | **aborted** |
| **V5** | **plain chat turn 1** (head + question) | **30 s** | **chat turn 2** (turn 1 + reply + question) | **aborted** |
| V6 | V5 plus `--no-vbr-prompt-cache` | 30 s | same | alive, but **0 reused** (full 9,237 re-prefill) |

**4 of 4 abort when request 2 arrives after the idle capture has published** (about 4 s after release). The two
that arrived before it survived. V5 is ordinary chat.

## Scope and what is not known

- **Your own sessions today do not show it.** The proxy log has continuous serving from 15:42 to 17:38 and from
  17:46 to 18:37, with no relaunch. So something in the repro differs from that traffic; this is not identified. One
  unexplained server stop falls between 14:22 and 15:38, during the NP4 incident work.
- **Mitigations tried:** `--no-vbr-prompt-cache` avoids the abort but disables reuse entirely (V6), which costs a full
  re-prefill every turn. The NP4 incident found the same for `--cache-ram 0`. **Neither is usable as a daily
  setting.** `-sm layer` has no meta buffer but halves decode and OOMs at depth on this config
  (`split-prefill-73/`).
- **Actions taken:** the wake proxy's automatic warm-up is OFF by default (`WP_WARM_ON_LOAD=0`) until fixed.
  Otherwise the daily config is unchanged.

## For buun

Repro: the flags above on 2x P100 `-sm tensor` with a qwen35 hybrid.
1. Send one ~9k-token chat.
2. Wait 30 s.
3. Send a second chat that extends it.

The script is `split-prefill-73/warm_crash_v5.py`. Asks:
- whether `ensure_vbr_replacement_recovery` should skip, or gather, meta-buffer recurrent tensors, as in the NP4 ask;
- whether `size % row_stride` fails because the recurrent state's row size is not divisible across the two
  tensor-split shards.
