# VERIFIED: buun's `a56eeef51` fixes tensor-split prompt caching on 2×P100

**Date:** 2026-09-07, 21:01 · **Node:** `.73`, 2× Tesla P100 (sm_60)
**Build:** `buun-llama-cpp` **`a56eeef5`** — *"server: bind tensor-split cache state to physical
devices"*, built at that exact commit (not HEAD), `build_a56`, binary 21:00:32
**Model:** `Qwen3.5-4B-Q5_K_S.gguf` · **Raw:** `raw_artbind_a56.log`, `raw_cacheab_a56.log`
Scripts unchanged from the failing run: `.73:~/artbind.sh`, `~/cacheab.sh`

## Binding — 5/5, was 3/5

| arm | split mode | tensor-split | `c9c52d71` (before) | **`a56eeef5` (after)** |
|---|---|---|---|---|
| A | tensor | automatic | `runtime_pools=2 bindings=0 lanes=0` **FAIL** | **`store ready … lanes=2`** |
| B | tensor | `1,1` explicit | `runtime_pools=2 bindings=0 lanes=0` **FAIL** | **`store ready … lanes=2`** |
| C | layer | automatic | `store ready … lanes=2` | `store ready … lanes=2` |
| D | layer | `1,1` explicit | `store ready … lanes=2` | `store ready … lanes=2` |
| E | layer | 1 GPU | `store ready … lanes=1` | `store ready … lanes=1` |

Both failing arms now bind. Nothing regressed.

## Cache reuse — the measurement, not the log line

Identical 4,010-token prompt sent twice, `-ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram 512M
--cache-ram 4096`:

| `-sm tensor` | pass 1 prefill | pass 2 prefill | pass 2 wall |
|---|---|---|---|
| `c9c52d71` | 4010 tok / 4528.47 ms | **4010 tok / 4527.29 ms** | 4.728 s |
| **`a56eeef5`** | 4010 tok / 4554.04 ms | **4 tok / 54.96 ms** | **0.261 s** |

**18.3× on wall clock.** `-sm layer` is unchanged (4 tok / 50.97 ms), confirming no regression
on the path that already worked.

## What the fix actually was

Broader than our report suggested — five files, plus 159 lines of new tests in
`test-llama-archs.cpp`. Our report named the right mechanism and the right symptom but pointed
at the wrong layer to patch.

We identified `server-context.cpp`, where each pool's `backend_device` is matched against
`live_device_domains` and both lookups missed. The old code tried to recover a physical device
from a Meta buffer type in that consumer:

```cpp
if (ggml_backend_buft_is_meta(buft)) {
    if (ggml_backend_meta_buft_n_bufts(buft) != 1) { complete = false; continue; }
    buft = ggml_backend_meta_buft_simple_buft(buft, 0);   // child 0 as if it were the whole
}
```

`a56eeef5` refuses to unwrap Meta there at all, and fixes the **producer** instead
(`llama-context.cpp`, `llama-kv-cache.cpp`, `llama-memory-recurrent.cpp`,
`llama-vbr-explicit-capture.cpp`) so physical rows arrive correctly. His new comment:

> *Tensor-split Meta allocations are expanded by the memory owner using their actual child
> buffers; topology weights are never substituted for measured resident bytes.*

That is a better fix than patching the `find_if` would have been, and it explains why one
symptom in one function required changes across five.

## Timeline

| time | event |
|---|---|
| ~09:00 | Reproduced on `c9c52d71` after a 445-commit rebuild |
| ~11:30 | Root-caused to `runtime_pools=2 bindings=0`; 5-arm discriminator isolates it to `-sm tensor`, not multi-GPU |
| ~11:40 | Reported to buun (2 messages), incl. two corrections to our own earlier framing |
| ~12:00 | Widened: **all** KV codecs affected, f16/q8_0 fail silently; fork-isolated with a 07-26→08-25 regression window |
| 13:17 | buun: *"I'm throwing Astra at it now"* |
| 17:59 | `a56eeef51` authored |
| 18:07 | buun: *"fixed"* |
| **21:01** | **Verified on 2×P100 by the reporter** |

## Limits

One node, one model, one KV config. Verifies the reported defect is gone and the previously
working paths still work; it is not a general regression suite. The `-np > 1` and 27B
production configurations were not re-tested.

---

## Production-config smoke test, 2026-09-08 09:57 — 41.6× on the real serving path

The verification above used a 4B with a minimal flag set. This repeats it against `.73`'s
**actual** serving model and flag surface. Raw: `raw_smoke_a56_prod.log`.

```
model   /mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf
flags   -fit off -c 262144 -b 1024 -ub 512 -ctk vbr -ctv vbr --vbr-floor 2.25 -cb -fa on
        -np 1 --kv-unified --cache-idle-slots -ngl 999 --reasoning on --cache-ram 2048
        -sm tensor -ts .85,1.15 --spec-type draft-mtp --spec-draft-n-max 2
        --chat-template-kwargs '{"auto_disable_thinking_with_tools": false,
                                 "preserve_thinking": true, "max_tool_response_chars": 100000}'
```

| | pass 1 | pass 2 | wall |
|---|---|---|---|
| `a56eeef5`, production flags | 4,052 tok / 27,518 ms | **4 tok / 195 ms** | **28.06 s → 0.67 s = 41.6×** |

`VBR_ARTIFACT_CAPTURE store ready … lanes=2` under `-sm tensor`, MTP draft context created,
every production flag accepted with no removed-flag errors.

**Not exercised:** `--mmproj` and `--chat-template-file` (both Qwen3.6 artifacts; the serving
model is 3.8), and `-np 2` (the live log shows `n_slots = 1`, so production is single-slot).

## Config drift found while setting this up

`.73`'s `~/.config/llama-swap/config.yaml` (written 2026-07-19) is stale three ways and would
not run as written:

| | config says | reality |
|---|---|---|
| binary | `~/buun_vbr/build/bin/llama-server` | **2026-07-26 build.** Predates the 07-26→08-25 regression window, so it has *partial* prefix reuse (516/4010 tokens), not the zero `c9c52d71` gives — it escaped the bug by being stale |
| model path | `/mnt/models/Qwen3.6-27B-Q6_K-MTP.gguf` | moved to `/mnt/models/AI_Models/Qwen 3.6/…`; every path in the file is stale by one directory level |
| model | Qwen3.6-27B-MTP | the box actually serves **Qwen3.8-27B-Q6_K** |

**Operator context (2026-09-08): llama-swap was deliberately retired on `.73`** — not a
temporary disable. Nothing currently needs it with Qwen3.8-27B as the single served model, so
the drift above is dead config for a retired subsystem, not a live hazard. Recorded because the
file is the first thing anyone would reach for to restart serving, and it would not start as
written.

**If it is ever revived**, the evidenced change is: point the production entry at
`~/buun-llama-cpp/build_a56/bin/llama-server`, fix the `AI_Models/` paths, and drop
`--chat-template-file buun_q36_chat_template.jinja` — that template targets Qwen3.5/3.6 and
**has no `reasoning_effort` branch at all** (introduced in 3.8's template), so applying it to a
3.8 model would silently remove the effort control. See
`qwen38-template/RESULT_TEMPLATE_AUDIT.md`; the 3.8 official template's live gap is the missing
`developer` role (buun fix #3), which matters when driving the model from Claude Code / Codex /
OpenCode.

The 41.6× above is what the binary change buys on the Hermes path. Not applied — production
config changes are the operator's call.
