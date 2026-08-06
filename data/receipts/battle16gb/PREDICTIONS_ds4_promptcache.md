# Predictions — does prompt caching make DS4-Flash usable multi-turn on 4×P100?

Logged **before** the run, 2026-08-01. `.194`, 4× Tesla P100-PCIE-16GB (1063 MHz / 150 W),
DS4-Flash UD-IQ1_S 82.5 GB, build `42974d12` (clean), config
`-c 8192 -ngl 99 -sm layer -ts 3,4,4,1 -fit off -fa on -ncmoe 40`.

## Why this and not ScrapeBench

`DS4_FLASH_P100_LOAD.md` measured **478 ms/token prefill** and named prompt caching as the
untested lever: *"long-context use is impractical without a prompt cache."* Running ScrapeBench
(14 turns, growing context) would spend hours re-confirming a prefill wall already measured —
it would fail on prefill, not on capability. This tests the lever directly.

The practical question behind it: can DS4-Flash serve as a research companion — multi-turn
chat, tool calls, reading files — or is 2.16 t/s decode plus a 478 ms/token prefill fatal?

## The mechanism being tested

llama-server reuses the longest common prefix of a request against cached KV. In multi-turn
chat, turn N's prompt is *exactly* turn N−1's prompt + assistant reply + new user message —
a pure prefix extension. So turn 2 should prefill only the new tokens (tens), not the whole
context (thousands). If that holds, the 478 ms/token wall is paid **once per conversation**
rather than per turn.

| id | claim | conf |
|---|---|---|
| P-C1 | with `cache_prompt`, turn-2 prompt-eval tokens drop ≥5× vs the no-cache arm | **0.80** |
| P-C2 | with cache, turn-2 and turn-3 wall-clock are each < 180 s | **0.60** |
| P-C3 | without cache, prompt-eval tokens grow monotonically each turn (full re-prefill) | **0.85** |
| P-C4 | output stays coherent across 3 turns (gzip 0.42–0.60, CJK 0) | **0.70** |
| P-C5 | cache works **despite `-ncmoe 40`** CPU expert offload | **0.75** |

## Reasoning

**P-C1 = 0.80.** Prefix reuse is standard, arch-independent llama-server behavior. Held below
0.9 because DS4 is a brand-new architecture with a compressor/indexer path, and this fleet has
already found DS4-specific gaps in code that was "arch-independent" in principle — the
tensor-split regexes being today's example.

**P-C2 = 0.60, the weakest.** Even with a perfect cache hit, *decode* is untouched: 200 tokens
at 2.16 t/s is 93 s before any prefill. So the ceiling for a useful answer is ~2–3 min/turn
regardless. This asks whether the total lands somewhere a human would tolerate, and it is
close to the line by construction.

**P-C3 = 0.85.** This is the control. If the no-cache arm does *not* grow, the instrument is
broken — it would mean caching is on regardless of the flag, and P-C1 would be measuring
nothing. Recent llama-server defaults `cache_prompt` to true, so this arm must be explicit.

**P-C5 = 0.75.** The prompt cache stores KV, which lives on GPU; `-ncmoe` offloads *expert
weights* to CPU. These should be orthogonal. But every DS4 assumption of orthogonality tested
today has held only after checking, so it gets its own line rather than being assumed.

## What would make this a negative result worth publishing

If caching does **not** engage (P-C1 falsified), DS4-Flash on 16 GB-class hardware is
confirmed unusable for anything multi-turn, and the "research companion" framing in
`DS4_FLASH_P100_LOAD.md` should be retracted rather than softened. That is a useful finding:
it would mean the model runs, generates coherently, and still cannot hold a conversation.

## Measurement

Per turn, from the server log: `prompt eval time = X ms / N tokens` and
`eval time = Y ms / M tokens`. **N is the load-bearing number** — it reports how many prompt
tokens were actually processed rather than reused, so it distinguishes a cache hit from a fast
re-prefill. Wall-clock is recorded too but is the coarser signal.
