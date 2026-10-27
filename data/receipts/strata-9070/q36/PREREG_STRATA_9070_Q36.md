# PREREG -- Strata 0.2.7 vs upstream llama.cpp on Qwen3.6-35B-A3B, spilling on a 16 GB RX 9070 XT

**Registered 2026-10-27, before any timed run.**

**Prior art checked:** `ledger_precheck.py "Strata Qwen3.6 9070 hybrid expert cache"` -> INDEX L557 (Strata v0.1.39 on
this card, Flash-Next Coder IQ1_M: 52.6 tok/s, 2.57x llama.cpp's static `-ncmoe 28`), L558/L560/L565 (P100 panels:
a tie when everything is resident, 1.43-1.86x under spill). Strata's own `docs/QWEN36.md` (v0.2.7) reports, verbatim:
"| R9700 32 GB, UD-Q4_K_XL | 1 | 83.9 | 73.8 | 1.14 |" and "| RTX 3060 12 GB, hybrid (llama.cpp `-ncmoe 28 -t 8`, the
best split of a sweep) | 1 | 64.0 | 41.1 | 1.56 |" (Strata tok/s | llama.cpp | ratio, one request, MTP off). **What this
adds:** the RX 9000 hybrid-mode case those tables lack, on Strata's current release, and a new model family on this card.

## Setup

- **Model:** Unsloth `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`, 22,360,456,160 B, sha256 `707a55a8...` (repo `unsloth/Qwen3.6-35B-A3B-GGUF`,
  rev `a483e9e6`). **It has no MTP layer** (40 blocks, no nextn tensors). Strata pins the MTP variant
  (`unsloth/Qwen3.6-35B-A3B-MTP-GGUF`, 22,853,663,008 B) for its drafts, so **both engines run without speculation**,
  which is also how Strata's published comparison ran. An MTP pair is a possible later addendum.
- **Strata:** v0.2.7 (`5e8a4cca`); setup compiled the engine from that source (0.1.52 package verified and unpacked
  first; setup preferred its own build). Config `strata-qwen36-ud-q4_k_xl.json` as setup wrote it (`--native`,
  `--max-context 32768`, `--prefill auto`, parallel 1) with `--mtp 2` removed. Thinking off through the server's shared
  setting `reasoning_effort: none`.
- **llama.cpp:** upstream `f74e2fa` ROCm build, `-ngl 99 -fa on -c 32768 -ctk f16 -ctv f16 -np 1 -t 8 -fit off`,
  `--chat-template-kwargs '{"enable_thinking":false}'`. `--n-cpu-moe` by sweep: K_min = the fewest CPU expert layers
  that load and answer a smoke request (from 12 upward in steps of 2), then K_min, K_min+2, K_min+4 on code-v1; the
  fastest is "best" and runs reasoning-v1.
- **Workload:** lmx `speed-test run custom --mode remote`, the same client for both engines, `--max-tokens 256`,
  canonical code-v1 and reasoning-v1 prompts (the files from the October panel), 1 warm-up + 3 timed, median decode
  tok/s. A capture proxy records the text. Fresh server per arm.
- **Arms:** S_code x2 fresh starts, S_reason x1; L sweep (3 x code-v1), L_best_code x1 more fresh start, L_best_reason x1.
- **Isolation:** the whole chain runs in one systemd unit with `MemoryMax=26G` (both servers inherit it), Clef paused
  and restored by ExecStopPost. Desktop RAM 31 GB, swap is zram.

## Predictions

| # | claim | rule |
|---|---|---|
| P1 | Strata decodes faster than llama.cpp's best split by at least 1.4x, between Strata's own spill (1.56x) and resident (1.14x) figures | median S / median L_best >= 1.4 on code-v1 AND on reasoning-v1 |
| P2 | Strata's adaptive expert cache serves most routed lookups from VRAM | its logged decode expert-cache hit rate >= 70 % |
| P3 | Both engines finish without tripping the memory cap | no OOM kill; unit memory peak recorded |

Reported: TTFT, prompt tokens, start-to-start spread (two S_code starts), VRAM/RAM at load, the full llama.cpp sweep,
and whether both arms' text stays sensible (capture).

## Addendum 1 -- the MTP variant of the file, and an MTP pair (registered 2026-10-27, before any timed run)

**Launch 1 aborted before any measurement:** Strata's Qwen3.6 engine path requires the MTP metadata
(`strata-q36: missing qwen35moe.nextn_predict_layers`), so it cannot run the plain file at all. The chain was stopped
before the llama.cpp sweep produced a number. **Both engines now use the file Strata pins:** Unsloth
`unsloth/Qwen3.6-35B-A3B-MTP-GGUF` rev `5bc3e238`, `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`, 22,853,663,008 B, sha256
`55983c5a75a1...` (verified before use). The plain file is retired.

**Added arms (same file, same harness):** S_mtp_code and S_mtp_reason (setup's config as written, `--mtp 2`);
L_mtp_code and L_mtp_reason (llama.cpp best split plus `--spec-type draft-mtp`; if the draft head does not fit at the
best split, the next split up, recorded). The no-MTP arms and P1-P3 are unchanged and stay primary.

| # | claim | rule |
|---|---|---|
| P4 | Strata's MTP drafts pay off on this card | median S_mtp / median S (no MTP) >= 1.2 on code-v1 |
| P5 | Strata's lead holds with speculation on both sides | median S_mtp / median L_mtp >= 1.4 on code-v1 |
