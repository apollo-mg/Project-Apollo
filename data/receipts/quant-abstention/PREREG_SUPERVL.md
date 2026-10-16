# Pre-registration -- Nemotron 3.5 Super VL 120B-A12B (UD-Q2_K_XL) on the quant-abstention instrument, against Flash-Next Q2

**Registered 2026-10-15, before any Super VL row was collected and before the file is on .194.** Mark's question: Super
VL is the Nemotron pitched against Flash-Next; does it know as much, and does it confabulate less? Bolt 74B, the 2-bit
QAT demonstration, refused only 0.16 of invented items (`RESULT_BOLT.md`), which sets the family prior.

**Prior art checked:** `ledger_precheck.py "quant-abstention UNKNOWN abstention"` -> `RESULT_FLASHNEXT.md` (FNQ2: easy
0.90, hard 0.79, invented refused 0.71), `RESULT_BOLT.md` (0.675 / 0.41 / 0.16), `RESULT_MAIN.md` (27B Q8_0:
0.85 / 0.50 / 0.60). **What this adds:** the head-to-head Mark asked for, on the same host and placement as FNQ2.

## Instrument (as `PREREG_FLASHNEXT.md` and `PREREG_BOLT.md`, except where stated)

- **Runner, corpus, grading unchanged:** `run_main.py`, `corpus/M1` (40 E, 100 H, 100 U), thinking off, greedy,
  `max_tokens` 1024, `cache_prompt` false, one discarded warm-up.
- **Host (as FNQ2):** .194, 4x Tesla P100, 150 W / 1063 MHz, read back and recorded. `GGML_CUDA_ALLREDUCE=internal`.
- **Build (differs from FNQ2):** upstream llama.cpp v0.7.0 `620d222` (`~/llama.cpp-v0.7.0/build_sm60` on .194; same
  commit and recipe as .73's). buun `0b2789f23`, FNQ2's build, cannot load `nemotron_h_moe`.
- **Server flags (as FNQ2):** `-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off -lv 4`, all four GPUs, no
  mmproj, no MTP/drafter, fresh server.
- **Arm SVQ2:** `unsloth/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-GGUF`, `UD-Q2_K_XL/` 3 shards, 57,788,537,768 B
  (lfs oids `04732951...`, `d86ba79d...`, `6282f2c8...`; sha256 verified after download).
- **Placement:** fully GPU-resident if it loads at the flags above. If it does not, the routed experts of the last K
  layers go to CPU via `-ot`, starting at K = 2 and stepping by 2 (FNIQ4's procedure), recorded as a deviation. FNQ2
  vs FNQ2X showed placement does not move grades on this instrument (`RESULT_FLASHNEXT.md`, P4).
- **Bytes are not matched:** the label and packager match FNQ2 (unsloth UD-Q2_K_XL), but Flash-Next's file is
  78,869,128,864 B, of which ~28.8 GB is per-layer embedding tables kept in host memory. Reported as is; no
  byte-matching claim is made.
- **Tokenizer:** the " UNKNOWN" / " Unknown" / " unknown" ids are recorded at the start; the slot readout is
  secondary and reported only if all three are single tokens.
- **References (stored, not rerun):** `raw/main_FNQ2.jsonl`, `raw/main_BOLT.jsonl`, `raw/main_C.A.jsonl`.

## Readouts and analysis (`analyze_supervl.py`, committed with this file, self-tested on stored arms)

E and H accuracy, H timidity, U refusal (complement confabulation), TRUNCATED as neither. Paired by item, 95 %
percentile bootstrap, 10,000 resamples, seed 20261016.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **Super VL knows less than Flash-Next Q2** | H acc SVQ2 - FNQ2 <= -0.05, CI upper < 0 | 0.6 |
| P2 | **Super VL confabulates more than Flash-Next Q2** | U refusal SVQ2 - FNQ2 <= -0.10, CI upper < 0 | 0.6 |
| P3 | **Super VL knows more than Bolt** | H acc SVQ2 - BOLT >= +0.10, CI lower > 0 | 0.75 |
| P4 | **Super VL confabulates less than Bolt** | U refusal SVQ2 - BOLT >= +0.10, CI lower > 0 | 0.55 |
| P5 | **Thinking off keeps answers short** | TRUNCATED <= 2 % of 240 | 0.85 |

Reported without a prediction: SVQ2 vs the 27B Q8_0 on H accuracy and U refusal; E accuracy; the slot readout if valid.

## Stop rules

As `PREREG_BOLT.md`: non-empty smoke and warm-up; `reasoning` empty on every row (else a logged deviation); a server
death resumes on a fresh server, recorded.
