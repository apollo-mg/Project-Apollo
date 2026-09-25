# .73 at depth: prefill 151 -> 99 tok/s and decode 27 -> 8 tok/s from 2k to 128k under tensor split; layer split as configured cannot serve 64k+ or -np 4; no VBR sticky floor in llama-server

**2026-09-24**, `.73` (2x P100, 1063 MHz / 150 W), buun `08826ad6e` `build_sm60_0920`, the daily-driver wake-proxy
flags (`Qwen3.8-27B-Q6_K` + mmproj, `-c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -fa on
--spec-type draft-mtp --draft-max 3 --kv-unified`), changing only `-sm` and `-np`. Prereg:
`PREREG_SPLIT_PREFILL_73.md`. Harness `bench73.py` / `run_legs.sh`. Raw: `raw/*.jsonl`, server logs `raw/logs/*.log.gz`
(home paths redacted). Fresh server per leg, one discarded warmup, raw token ids, `cache_prompt: false`, 256 tokens
decoded at temperature 0.

## Tensor split (as served): the depth curve

| prompt | prefill tok/s (average over the prompt) | decode tok/s at that depth | MTP accept | kv_bpv after |
|---:|---:|---:|---:|---:|
| 2k | 151.4 | 24.7 | 86 % | 16.0 |
| 16k | 147.2 | 26.7 | 95 % | 16.0 |
| 64k | 122.9 | 15.5 | 89 % | 9.60 |
| 128k | **99.4** | **8.0** | 68 % | 5.83 |

- **Reading 128k tokens takes 22 minutes.** The earlier 149 tok/s figure held only for short prompts.
- **Decode falls 3.3x from 16k to 128k.** VBR makes KV *memory* elastic, but attention compute still grows with
  depth.

## Layer split (`-sm layer`, default split)

| prompt | prefill tok/s | decode tok/s | notes |
|---:|---:|---:|---|
| 128k | -- | -- | HTTP 500: `f16 dequant scratch reserve failed (device memory exhausted)` |
| 64k | -- | -- | same |
| 16k | 145.4 | 13.9 | kv_bpv already at the floor (4.22) |
| 2k | 102.4 | 15.3 | |

The layer-split log carries a warning the tensor-split log never shows: `VBR budget 9088.00 MiB exceeded with the
degrade order clamped at the --vbr-floor (projected 258.00 MiB at 12288 cells)`. VBR hit its floor at 12k cells
despite a 9 GB budget. The likely cause is one card starved by the drafter and mmproj landing on it (the pattern in
`drafter-gates-kv-budget`). The logs carry no per-device breakdown, so that is **unverified**.

**`-np 4 -sm layer` (L4):** no abort, and the server was healthy at the end. But **every request failed** with
`CUDA pool allocation failed (out of VRAM)` inside the MTP draft context. The workaround BACKLOG listed for the
`-np 4 -sm tensor` crash does not work as configured.

## Warm-head feasibility probe (for a wake-proxy pre-warm of Hermes's system prompt + tools)

`warm_head_probe.py`, daily config, `-np 1`. Synthetic Hermes-shaped head: 30k chars of system text ending in a
Hermes-style date line, plus 6 tool schemas. The Qwen3.8 template renders the tools first, then the system text.
Raw: `raw/warm_head_probe.jsonl`.

| step | cached | prefilled | wall |
|---|---:|---:|---:|
| 1. cold: head + question A (through the proxy, includes the 35 s load) | 0 | 8,172 | 90.6 s |
| 2. unrelated request (evicts the slot) | | | |
| 3. warm-up: raw `/completion` of the rendered head, **cut exactly where the user turn starts** | | 8,150 | 53.8 s |
| 4. head + a *different* question B | **8,150** | **16** | **2.1 s** |

**The whole head is reused on the hybrid model** when the warm-up ends exactly at the user-turn boundary. The server
then holds a restorable state at that point, which the recurrent layers require. Rendering comes from the server's
own `/apply-template`, so the cut is byte-exact. The wake proxy forwards only `/v1/*`, `/props` and `/slots`, so a
pre-warm has to call `/apply-template` and `/completion` on the node directly (steps 2-4 did).

**Built into the wake proxy the same day** (`modules/wake_proxy.py`, CHANGELOG). Live end-to-end test,
`warm_proxy_e2e.py` -> `raw/warm_proxy_e2e.jsonl`:
- A Hermes-shaped chat stamped with *yesterday's* date was captured (9,123 tokens, cold 61.6 s).
- `POST /warm` re-dated it, reused 8,607 tokens (the nearest saved state before the date line), prefilled 499, and
  took 3.8 s.
- A request with today's date and a new question then reused **9,106** tokens, prefilled 15, and took **1.33 s**.
- The automatic post-load leg did not run: `/suspend` answered 409 because .73 was genuinely busy (98 % GPU, a
  real 8k request in the slot).

## Scored against the prereg

| # | claim | result |
|---|---|---|
| P1 | tensor prefill > layer prefill at every depth | 16k: 147.2 vs 145.4 (tie); 2k: 151 vs 102. **VOID** at 64k/128k (layer failed) |
| P2 | tensor decode > layer decode at every depth | **TRUE where measured**: 1.92x at 16k, 1.61x at 2k |
| P3 | prefill falls with depth | **TRUE** for tensor (151 -> 147 -> 123 -> 99). Layer: too few points |
| P4 | L4 survives the reuse matrix | **TRUE as worded** (no abort), but hollow: 0 of 6 requests served |
| P5 | L4 turn 3 reuses the prefix | **VOID** (nothing served) |
| P6 | the VBR floor is sticky in llama-server | **FALSE.** Each new prompt logged `vbr reset ... re-enters at the entry tier` (degrade cursor 55 after 128k, 26 after 64k), and kv_bpv followed each prompt's depth (5.83 -> 9.60 -> 16.0 -> 16.0). The server log agrees with `/slots`. |

**Mark's recollection ("tensor split buys decode, pays a prefill penalty"):** the decode half holds. No prefill
penalty was seen: at 16k the two modes tie, and at 2k tensor is faster.

## What it changes

- **Hermes compaction on .73.** Measured rates:
  - summarizing a ~240k history costs roughly 45+ minutes (extrapolated past 128k; at least 22 min per 128k read);
  - the lean regime's re-prefill (~20-25k tokens) costs ~2.5-3 min;
  - "95 % -> keep 50 %" costs about 20 min of summary read plus about 20 min of re-prefill **per compaction**, and
    every turn in between decodes at single-digit tok/s near 250k.
- **A warm Hermes head** (~25k tokens) saves about 2.8 min per cold session start.
- **`-np 4` on .73 needs buun's fix for tensor split.** Layer split halves decode and, as configured, cannot serve
  anything at `-np 4`.
- **Buun asked about the sticky floor:** llama-server on `08826ad6e` resets cleanly between unrelated prompts.
  AFM-46 remains a `llama-perplexity` / unfrozen-budget observation.

## Not established

- One run per depth.
- Layer split was not balanced with `-ts`, so these numbers describe this config, not layer split in general.
- Beyond 128k is extrapolated.
- The 2k probe runs after the 16k request, so its prefill includes any transcode back from the previous state.
