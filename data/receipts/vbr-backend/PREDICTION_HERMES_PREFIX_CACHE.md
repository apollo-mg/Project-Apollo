# Pre-registration — does the third draft hit the prompt cache?

**2026-09-06, before the run.** `.73` (dual Tesla P100, sm_60), Hermes Agent against the local
llama-server, Qwen3.8-27B Q6_K. Same conversation that already contains draft 1 and draft 2;
Mark sends the final draft as a third message.

## Setup

Turn 1 (draft 1) and turn 2 (draft 2) are already in the conversation history. Turn 3 sends a
third document. The shared prefix is everything before the new PDF's text — system prompt,
draft 1, its critique, draft 2, its critique.

## What decides the answer

`llama-server` reports `prompt_n` (tokens prefilled) and, on a cache hit, a much smaller
number than the full context. The server log is authoritative; `/props` is not
(see `RESULT_VBR_FIDELITY.md`).

## Predictions

| # | prediction | conf |
|---|---|---|
| P1 | The shared prefix IS reused — `prompt_n` on turn 3 is far below total context | 0.70 |
| P2 | Time-to-first-token on turn 3 is materially shorter than turn 2's (which ran >15 min) | 0.65 |
| P3 | Prefill of the NEW document still dominates the wait — the delta is ~5k tokens on a P100 | 0.75 |
| P4 | Total wait is still measured in minutes, not seconds, even with a cache hit | 0.80 |

**P1 is the load-bearing one.** If the prefix is NOT reused, every turn in a long document
review re-prefills the entire conversation, and cost grows quadratically with turns. That
would be a real finding about the harness, not the model.

**Failure mode to watch for:** if Hermes rewrites or re-orders the system prompt between
turns (injecting a timestamp, reordering tools), the prefix breaks and the cache misses even
though the conversation looks continuous. That is the most likely cause if P1 fails, and it
is a harness bug rather than a llama.cpp one.

## Method

1. Wake `.73`, confirm the server is up and note the model.
2. Capture the server log position before the request.
3. Mark sends the final draft in the existing conversation.
4. Read `prompt_n`, `prompt_ms`, `cache_n` and the predicted-tokens rate from the server log.

Nothing here is measured yet. `.73` was asleep at the time of writing.
