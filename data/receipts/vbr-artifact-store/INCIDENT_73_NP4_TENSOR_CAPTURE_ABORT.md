# Incident — `-np 4` + `-sm tensor` aborts llama-server in the VBR idle host-capture of recurrent state (.73, buun 08826ad6e)

**2026-09-24 14:16, `.73`** (2x P100, sm_60), buun `08826ad6e` (`build_sm60_0920`), the daily-driver config served
through the wake proxy. Full backtrace: `raw_73_np4_abort_backtrace.txt` (coredumpctl, home path redacted).

## Trigger

Mark saw `cache_n: 0` on turn 2 in Open WebUI. At `-np 1`, Open WebUI's follow-up, title and tag calls evict the
single slot (same mechanism as the desktop test earlier today). The fix tried was `-np 4`.

## The crash

Config: `-np 4 -sm tensor --kv-unified -ctk vbr -ctv vbr --vbr-floor t4 --spec-type draft-mtp --draft-max 3`,
`Qwen3.8-27B-Q6_K` (qwen35 hybrid: attention + recurrent layers), default `--cache-ram` (host prompt cache ON).
The first multi-turn request after start killed the server with SIGABRT:

```
#3  ggml_abort
#4  ggml_backend_meta_buffer_get_tensor            (libggml-base)
#5  chain_io_writer::write_tensor                   (libllama)
#6  llama_memory_recurrent::state_write_data
#7  llama_memory_recurrent::state_write
#8  recurrent_companion_capture
#9  vbr_capture_projected_batch
#10 server_vbr_artifact_store::capture_projected_host_batch
#11 server_context_impl::publish_idle_vbr_batch
```

When a slot goes idle, the server captures its state into the host artifact store. Reading the **recurrent**
companion state out of a **tensor-split (meta) buffer** hits one of the `GGML_ASSERT`s in
`ggml_backend_meta_buffer_get_tensor` (`ggml-backend-meta.cpp` ~1765-1786, all layout asserts). The assert text
was not recoverable: the second launch overwrote the server log, and it is not in the core.

A side effect: the proxy's 3 s `/health` probe failed during the abort window, and it launched a second server,
which failed to bind `:8080`.

## What reuses and what doesn't (same client test each time: turn 1, turn 2, a title-style side request, turn 3)

| config | turn 2 (consecutive) | turn 3 (after side request) | stable |
|---|---|---|---|
| `-np 1`, host cache on (original) | **2,423 reused, 1.0 s** | 0 reused, 17.7 s | yes |
| `-np 4`, host cache on | — | — | **SIGABRT** |
| `-np 4 --cache-ram 0` | 0 reused, 17.4 s | 0 reused, 18.2 s | yes |

On this hybrid model under dynamic VBR, **prefix reuse runs through the host artifact store**. Turning it off
(`--cache-ram 0`) disables reuse entirely, even for consecutive turns. The desktop 9070 (single GPU, no meta
buffer) reused fine with `-np 2`, so the crash is specific to tensor split with the recurrent capture.

## Resolution for today

`.73` is back on `-np 1` with the host cache on (stable, and consecutive turns reuse). The only change kept is
`--vbr-floor t2 -> t4`. The side-request eviction is handled on the client (Open WebUI's task and follow-up settings)
until this is fixed upstream.

## For buun

Repro: the flags above on any 2-GPU `-sm tensor` hybrid (qwen35) model, then two sequential chat requests. Asks:
- which assert fires (a debug run will print it);
- whether idle capture should skip, or gather, meta-buffer recurrent tensors;
- whether `-sm layer` avoids it (it should, since there is no meta buffer).
