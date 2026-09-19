# Result -- RST charters (a) coherence and (e) REST conformance: both pass at the documented gate

**2026-09-18.** Charters (a) and (e) of S4 in Avarok-Cybersecurity/atlas#1126, on the RX 9070 XT
(16 GB, desktop co-resident), Ornith-1.0-9B-NVFP4, SCALE 1.7.1, seq 4096 / batch 1.

**Run with TheTom's own scripts this time**, not reconstructions. The `kit/` tools the PRD invokes
are published at `gist.github.com/TheTom/45b80d669eb2fe95383eb57ae5d4b444` (8 files:
`oracle-run.py`, `oracle-prompts.jsonl`, `oracle-compare.py`, `rest-conformance.py`,
`kernel-census.sh`, `probe-lds-fp8.sh`, `probe-gpu.sh`, `README.md`). That resolves the S1
blocker: the scripts were never missing, only not in the repo. All are stdlib-only Python and
bash, no installs.

## Charter (a): 9 of 10 canaries, and the failure is the predicted one

Gate: *"readable, context-dependent outputs; 17 times 23 -> 391; canaries 9 of 10, the known
exception is the string-reversal task."*

40 prompts, temperature 0, thinking off, `max-tokens` at the script default of 64.
**40 of 40 returned, 0 errors, 0 empty outputs, 25.3 s total.**

| canary | expected | got | |
|---|---|---|---|
| p01 arithmetic | `391` | `391` | PASS |
| p02 arithmetic | `24` | `24` | PASS |
| p03 arithmetic | `1024` | `1024` | PASS |
| p06 unit-conversion | `250` | `250` | PASS |
| p07 unit-conversion | `180` | `180` | PASS |
| **p08 string-manipulation** | `salta` | `stalta` | **FAIL (documented)** |
| p09 factual | `Tokyo` | `Tokyo` | PASS |
| p10 factual | `Ottawa` | `Ottawa` | PASS |
| p11 code | `55` | `55` | PASS |
| p12 code | `81` | `81` | PASS |

**9 of 10, exactly the gate**, and the single failure is p08, the string reversal the charter
names in advance as the expected exception. Reversing "atlas" produced `stalta`: the right five
letters in nearly the right order, which is the classic tokenizer-level character-manipulation
failure rather than anything hardware-shaped.

Scored with `oracle-compare.py` (their canary logic, case-insensitive substring) rather than my
own, so the number is directly comparable to any R9700 run.

Non-canary output was coherent and input-dependent across every category, including both
multilingual prompts (Spanish and French answered in-language).

## Charter (e): 9 PASS, 1 FAIL, exactly as predicted

Gate: *"9 PASS, 1 FAIL expected; the known FAIL is an unknown model id answering 200 (#1121)."*

```
SUMMARY gfx1201: 9 PASS, 1 FAIL, 0 WARN, 5 INFO in 20.1s
```

| check | result |
|---|---|
| models_list | PASS |
| chat_nonstream | PASS |
| chat_stream | PASS (13 chunks, `[DONE]` seen) |
| max_tokens_honored | PASS |
| stop_honored | PASS |
| determinism_temp0 | PASS (identical across two calls) |
| invalid_json_body | PASS (HTTP 400, not a 5xx) |
| concurrency_8 | PASS (8 of 8, p50 2.59 s, p95 4.14 s) |
| long_prompt_ttft | PASS (TTFT 8.521 s on ~2973 tokens) |
| **unknown_model** | **FAIL -- HTTP 200, want 400/404** |
| n_parameter, logprobs, completions_legacy, response_format_json, tool_call | INFO (all supported) |

The counts land on the documented expectation exactly, and the one FAIL is the known #1121
defect. Nothing here is board-specific.

## The incidental finding: this card is compute-identical to the R9700

`scaleinfo` reports **32 multiprocessors** on the RX 9070 XT. `kernels/r9700/HARDWARE.toml`
declares `sm_count = 32` for the Radeon AI PRO R9700, with the comment explaining that RDNA 4
pairs two CUs into one WGP and SCALE reports WGP count. Both boards are 64 CU / 32 WGP.

**The two parts differ in VRAM and memory bandwidth, not in compute units.** Charter (e)'s
prefill number is consistent with that: TTFT 8.521 s on roughly 2973 tokens here, against the
#1107 reference of "TTFT 8.6 s on 2494-token prompt" on the R9700.

**Stated carefully: these are not matched conditions.** Different prompt text, different token
counts, and I did not run the R9700 figure myself. The honest claim is that prefill latency is in
the same band on both boards at roughly the same prompt size, which is what identical WGP counts
predict. A controlled comparison would need the same prompt on both, which needs TheTom's
hardware.

If it holds up, the practical reading is that a ~16 GB consumer 9070 XT buys the same compute as
the workstation part and gives up VRAM headroom, which is exactly the tradeoff charter (b) already
characterised from the memory side.

## Status of S4

| charter | status |
|---|---|
| (a) coherence | **PASS** -- 9 of 10 canaries, known exception |
| (b) VRAM boundary | **done**, gate needs rewording (see `RESULT_S4b_VRAM_BOUNDARY.md`) |
| (c) cancel/recovery | not started |
| (d) sustained decode, 10 min | not started -- needs the headless decision |
| (e) REST conformance | **PASS** -- 9 PASS / 1 FAIL, known defect |
| (f) concurrency soak, 30 min | not started -- gates on flat VRAM, needs the headless decision |

Artifacts: `logs/charter-a/oracle_gfx1201.jsonl` (40 records), `logs/charter-a/compare.json`,
`logs/charter-e/rest_gfx1201.json`.
