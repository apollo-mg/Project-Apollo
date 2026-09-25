# Static KV (turbo8/turbo4 or q8_0/turbo4) sidesteps the VBR tensor-split abort on .73: no crash after idle, and `-np 4` keeps each conversation's cache through side requests

**2026-09-25 10:40-11:25, `.73`** (2x P100, `-sm tensor`), the **daily build** buun `08826ad6e` and the daily flags,
changing only the KV (`-ctk`/`-ctv`, no `--vbr-*`), `-np` and the context. Harness: `static_kv_test.py` ->
`raw/static_kv_test.jsonl`; logs `raw/logs_static_kv/*.log.gz` (home paths redacted). Motivation:
`vbr-artifact-store/INCIDENT_73_NP1_IDLE_REUSE_ABORT.md`. The abort lives in the VBR artifact store, which a static
cache never uses. The pairs are Mark's pre-VBR defaults.

**Prior art checked** (in the script header): INDEX L161, where `q8_0` + turbo4 aborted on buun `87c351d28`;
L162/L165, mixed stock types abort under `-sm tensor`; L154, stock-quantized K+V collapse on sm_60.

## Context: 262k does not fit with a static cache

At `-c 262144` the static cache left no VRAM for the mmproj, which loads after the context:
`cudaMalloc failed: out of memory` in `clip_model_loader::load_tensors` (884.62 MiB). VBR sizes itself to the
remaining VRAM, so this never came up with it. Every run below uses **`-c 131072`**.

## Results (same ~9.2k-token head as the abort repro; temperature 0)

| config | test | outcome |
|---|---|---|
| turbo8 / turbo4, `-np 1` | turn 1, **30 s idle**, turn 2 extending it (the abort repro) | alive; turn 2 **reused 9,210**, prefilled 27 |
| turbo8 / turbo4, `-np 4` | turn 1, turn 2, side request, turn 3, then side request concurrent with turn 4 | alive; turn 2 reused 9,210; side request in its own slot; **turn 3 reused 9,260 after the side request**; concurrent side (543 reused) and turn 4 (9,297 reused) both served |
| q8_0 / turbo4, `-np 1` | abort repro | alive; reused 9,210 |
| q8_0 / turbo4, `-np 4` | reuse matrix | alive; identical pattern (9,210 / 9,260 / 9,295 reused); coherent replies |

**Decode:**
- About 24-25 tok/s on a warm turn with ~9.2k context. VBR's daily config did 24.7 at 2k and 26.7 at 16k.
- About 11 tok/s on the cold first turn, which includes MTP ramp-up.
- Two concurrent requests shared the cards at roughly 6-10 tok/s each.

## The automatic warm-up on this config, live (2026-09-25 14:46-14:52)

With the static config and `WP_WARM_ON_LOAD=1`:
- `.73` was asleep. A `GET /props` through the proxy (what Hermes does at startup) woke it (10 s), loaded the
  server (35 s), and then **warmed the captured real Hermes head by itself: 16,028 tokens in 109.9 s**.
- A Hermes-shaped chat through the proxy (same system prompt and 25 tools, top-level `reasoning_effort: xhigh`, a new
  question) then **reused all 16,028 tokens, prefilled 15, and answered in 3.1 s** (about 115 s cold).
- `/apply-template` renders a top-level `reasoning_effort` identically to `chat_template_kwargs` (and differently
  from no effort), so the warm-up renders the same head Hermes sends.

## What it means

- **Both of today's daily-driver problems go away with a static pair:** the idle-reuse abort, and the single-slot
  eviction (Open WebUI and Hermes side calls now run in their own slot without evicting the conversation).
- **Cost:**
  - context halves to 128k (decode is already ~8 tok/s at 128k on this box);
  - static KV is lossy at every depth, where VBR is bit-exact until pressure. This pair's fidelity is not measured;
    symmetric turbo4 is 0.016 KLD at 16k (`vbr-rd-194`), so turbo8 K should be lower.
- **`q8_0` + turbo4 works on this build**, so the August abort (INDEX L161) was specific to that commit.

## Not established

- One run per config, a 9.2k-token conversation, no depth sweep.
- No fidelity measurement for these exact pairs.
- The largest context that still fits with the mmproj (between 128k and 262k) was not searched.
