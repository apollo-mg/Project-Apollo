# Pre-registration -- Nemotron 3.5 Bolt 74B-A9B (NVIDIA's 2-bit QAT GGUF) on the quant-abstention instrument, against Flash-Next Q2 and the 27B Q8_0

**Registered 2026-10-15, before any Bolt M1 row was collected.** Bolt has run on .73 today only for speed and the
pelican (`nemotron-bolt/SPIN_BOLT74B_P100_LILICORR.md`, `svgbench-bolt/`). No M1 item has been sent to it.

**Prior art checked:** `ledger_precheck.py "quant-abstention UNKNOWN abstention"` -> `RESULT_FLASHNEXT.md` (Flash-Next
UD-Q2_K_XL: easy 0.90, hard 0.79, invented refused 0.71, hard abstained 0.01; 27B Q8_0: 0.85 / 0.50 / 0.60 / 0.03),
`RESULT_MAIN.md` (23 arms of the 27B), `RESULT_PILOT.md`. **What this adds:** a third model family on the instrument
(NVIDIA's nemotron_h_moe, hybrid Mamba/attention latent MoE), and the first quantisation-aware-trained 2-bit model on
it. Mark's question: Bolt is pitched against Flash-Next's tier; does it know as much, and does it confabulate less?

## Instrument (as `PREREG_FLASHNEXT.md`, except where stated)

- **Runner, corpus, grading unchanged:** `run_main.py`, `corpus/M1` (240 items: 40 E, 100 H, 100 U), thinking off
  (`enable_thinking: false`), greedy, `max_tokens` 1024, `cache_prompt` false, CAL grading imported unchanged. One
  discarded warm-up (the runner's).
- **Host (differs):** .73, 2x Tesla P100 at 150 W / 1328 MHz, read back and recorded. Flash-Next ran on .194. The
  readout is greedy answers, so the clock does not enter; the numeric path of a different build and card count may
  move individual answers, as any cross-build comparison does.
- **Build (differs):** upstream llama.cpp v0.7.0 `620d222` (`/mnt/HDD/llama.cpp-v0.7.0/build_sm60`). The buun build
  Flash-Next used cannot load this architecture.
- **Server flags:** `-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off`, no drafter, no mmproj, fresh server.
- **Model:** `nvidia/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB-GGUF`, 22,018,326,528 B, sha256 `91d63363e782c8a3...`.
- **Client:** the desktop, through an ssh tunnel to the server's loopback port.
- **`--expect-variants` is not passed.** Bolt's tokenizer is not Qwen's; its ids for " UNKNOWN" / " Unknown" /
  " unknown" are recorded at the start. The forced-slot P(UNKNOWN) is secondary and is reported only if all three are
  single tokens.
- **References (stored rows, not rerun):** `raw/main_FNQ2.jsonl`, `raw/main_C.A.jsonl`.

## Readouts and analysis (`analyze_bolt.py`, committed with this file, self-tested on stored arms)

As `analyze_flashnext.py`: E and H accuracy (CORRECT), H timidity (ABSTAINED on H), U refusal (ABSTAINED on U, its
complement confabulation); TRUNCATED counts as neither. Paired by item; 95 % percentile bootstrap over items, 10,000
resamples, seed 20261015.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **Bolt knows less than Flash-Next Q2** | H accuracy BOLT - FNQ2 <= -0.05 with 95 % CI upper bound < 0 | 0.65 |
| P2 | **Bolt knows at least as much as the 27B at 8 bits** | H accuracy BOLT - 27B Q8_0 >= 0, CI lower bound > -0.05 | 0.55 |
| P3 | **Bolt refuses invented items at least as often as the 27B Q8_0** | U refusal BOLT - 27B Q8_0 >= 0, CI lower bound > -0.07 | 0.5 |
| P4 | **Thinking off keeps answers short** | TRUNCATED on <= 2 % of the 240 items | 0.85 |

Reported without a prediction: U refusal BOLT - FNQ2, E accuracy, H timidity, and the slot readout if valid.

## Stop rules

- The server must answer the smoke and warm-up with non-empty content; `reasoning_content` must be empty on every row
  (thinking really off). A row with reasoning text is a deviation, logged, not silently kept.
- One arm. If the server dies mid-run, the runner resumes on a fresh server (it skips ids already written); that is
  recorded as a deviation.
