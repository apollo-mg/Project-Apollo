# `--split-mode tensor` disables prompt-cache reuse for every KV codec, not just VBR

**Date:** 2026-09-07 · **Node:** `.73`, 2× P100 (sm_60) · **Build:** buun-llama-cpp `c9c52d71`
**Model:** `Qwen3.5-4B-Q5_K_S.gguf` · Raw: `.73:~/kvcodec.log`, `~/kvctrl.log`, `~/kv_*.log`, `~/kvc_*.log`

Widens `RESULT_TENSOR_SPLIT_BREAKS_BINDING.md`. That receipt found the VBR artifact store
failing to bind under tensor split. This one shows the artifact store is not the whole
story — **tensor split breaks prompt-cache reuse for f16 and q8_0 too**, which never touch
the artifact store at all.

## Result

Identical 4,010-token prompt sent twice per arm. Same flags throughout
(`-ngl 99 -c 32768 -np 1 -fit off -fa on --kv-unified --cache-ram 4096`), `max_tokens=8`,
temp 0. Split mode is the only variable between the two columns. Pass-2 prefill token count
is the measurement: 4010 = no reuse, 4 = full reuse.

| KV codec | `-sm tensor` pass 2 | `-sm layer` pass 2 |
|---|---|---|
| `-ctk f16 -ctv f16` | 4010 tok / 4517.64 ms | **4 tok / 50.84 ms** |
| `-ctk q8_0 -ctv q8_0` | 4010 tok / 4536.12 ms | **4 tok / 59.77 ms** |
| `-ctk q8_0 -ctv turbo3` | 4010 tok / 4547.41 ms | not run |
| `-ctk vbr -ctv vbr --vbr-floor t4` | 4010 tok / 4525.98 ms | **4 tok / 51.27 ms** (prior receipt) |

Under tensor split, every pass-2 lands within 20 ms of its own pass-1. That is not degraded
reuse, it is none.

**The control is what makes this a result.** Without the `-sm layer` column, the f16 row
could be a harness artifact — wrong flag, slot not retained, prompt not actually identical.
The same arms reusing perfectly under layer split rules that out and leaves split mode as
the only candidate.

## Why this matters more than the VBR framing

VBR is the only codec that **reports** the failure:

```
VBR_ARTIFACT_CAPTURE topology unavailable reason=runtime_pool_binding_failed
  devices=2 resolved_split=2 topologies=1 runtime_pools=2 bindings=0 lanes=0 attention_children=1
automatic dynamic VBR host caching fallback=live_only … cache-ram disabled
```

f16 and q8_0 emit **nothing**. No warning, no fallback notice, no diagnostic of any kind —
the server simply re-prefills every request forever. Anyone running `-sm tensor` with an
ordinary KV cache has been paying full prefill on every turn with no indication that a cache
was supposed to be helping.

That inverts how the bug reads. VBR is not the thing that is broken; VBR is the thing that
noticed.

## Open questions (not measured)

- Whether the artifact-store binding failure and the general slot-reuse failure share one
  root cause (a device-identity mismatch under the meta device) or are two independent
  bugs that both trip on tensor split. `runtime_pools=2 bindings=0` is consistent with the
  first but does not establish it.
- Whether upstream llama.cpp's `--split-mode row` loses prompt caching the same way. Not
  tested; no upstream build on this node. If it does, this is not fork-specific.
- `turbo3` under `-sm layer` was not run. Both other non-VBR codecs flip, so the conclusion
  does not rest on it, but the cell is genuinely empty.

## Correction to what was sent

The report handed to buun on 2026-09-07 scoped the repro as "any model with `-ctk vbr -ctv
vbr --vbr-floor t4 --cache-ram 4096` under `-sm tensor`". Everything in it is confirmed, but
the scope is too narrow: the VBR flags are not required to reproduce loss of caching, only
to see it reported. Sent before this test was run.
