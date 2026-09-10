# `-sm layer` restores measured cache reuse; `-sm tensor` re-prefills verbatim

**Date:** 2026-09-07 · **Node:** `.73`, 2× P100 · **Build:** `c9c52d71`
**Model:** `Qwen3.5-4B-Q5_K_S.gguf` · Raw: `.73:~/cacheab.log`, `~/cab_tensor.log`, `~/cab_layer.log`

Companion to `RESULT_TENSOR_SPLIT_BREAKS_BINDING.md`, which established that the artifact
store binds under `-sm layer` and not under `-sm tensor`. That was a log line. This measures
whether reuse actually follows.

Identical 4,010-token prompt sent twice to each arm, same flags apart from split mode
(`-ngl 99 -c 32768 -np 1 -fit off -fa on --kv-unified -ctk vbr -ctv vbr --vbr-floor t4
--vbr-vram 512M --cache-ram 4096`), `max_tokens=8`, temp 0.

| arm | store | pass 1 prefill | pass 2 prefill | pass 2 wall |
|---|---|---|---|---|
| `-sm tensor` | binding failed | 4010 tok / 4528.47 ms | **4010 tok / 4527.29 ms** | 4.728 s |
| `-sm layer` | ready, lanes=2 | 4010 tok / 4784.47 ms | **4 tok / 51.27 ms** | **0.286 s** |

Reuse follows binding. Under layer split the second pass evaluates 4 tokens instead of
4,010 — 16.5× on wall clock. Under tensor split the second pass is within 1.2 ms of the
first: no reuse at all, not partial reuse.

Cold prefill cost of layer split here is **5.4%** (838.13 vs 885.51 tok/s). That figure is
from a 4B model and should not be carried to the 27B — see the tradeoff note below.

## The tradeoff this creates

`qwen38-splitmode/RESULT_P100_SM_TENSOR.md` (2026-08-14) measured decode on this node:
`-sm tensor` 13.930 t/s, `-sm layer -ts 1,1` 8.540 t/s, single GPU 8.585 t/s. Tensor split
is **1.63×** and is the only mode that converts the second P100 into throughput; layer split
across two cards is inert (0.995× of one card). Those decode figures were taken on
`Qwen3.8-27B-UD-IQ3_XXS` at `-c 8192` without VBR — a different configuration from the
262144-context VBR server the prefill row below assumes. The table mixes two sources.

So the choice is real: layer split costs 39% of decode throughput and buys a working prompt
cache. For a 25k-token stable system prompt and ~800 generated tokens per turn:

| | prefill | decode | turn |
|---|---:|---:|---:|
| `-sm tensor`, every turn | 164.6 s | 57.4 s | **222 s** |
| `-sm layer`, warm turn | ~0 | 93.7 s | **94 s** |
| `-sm layer`, cold turn | 173–268 s | 93.7 s | 267–362 s |

Layer split loses the first turn and wins every turn after it by roughly 128 s. The cold-turn
range is wide because 27B prefill under layer split is **not measured** — the low end assumes
the 4B's 5.4% penalty carries, the high end assumes prefill scales like decode (1.63×).

Neither mode is the good outcome. If the pool binding is fixed, `-sm tensor` keeps 13.93 t/s
*and* skips the prefill: ~57 s per turn, ~3.9× better than either option above.
