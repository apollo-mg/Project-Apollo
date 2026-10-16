# Pre-registration -- Bolt with thinking ON on the full M1 instrument

**Registered 2026-10-16, before any row of this arm.** The 20-item probe (`EXPLORE_THINK_BOLT.md`) flipped 7 of Bolt's
confabulations to UNKNOWN with thinking on, past its registered bar of 5, with no control broken. Flips used a median of
1,112 completion tokens; the 13 that stayed wrong used 258. Mark: put a finer point on it.

**Prior art checked:** the probe; `RESULT_BOLT.md` (thinking off: easy 0.675, hard 0.41, invented refused 0.16);
`RESULT_BOLT_SPLIT.md`; the thinking-cap receipts (a 512-token cap turned one correct abstention into an invented
answer); AbstentionBench (outside: reasoning fine-tuning cuts abstention ~24 %). **What this adds:** a within-model,
item-paired thinking off -> on comparison on M1, for the model whose reward model penalised reasoning length.

## Arm

- **BOLTTHINK:** NVIDIA's Bolt 24GB GGUF (the `BOLT` file, sha256 `91d63363...`), .73, upstream v0.7.0, `-ngl 99 -sm
  layer -c 12288 -ctk f16 -ctv f16 -np 1 -fit off` (context raised from BOLT's 4096 so thinking fits).
- **Runner:** `run_main.py --thinking --max-tokens 8192`. The `--thinking` flag (added today, default off, so earlier
  arms are unchanged) sets `enable_thinking: true` on R-gen only; R-slot is unchanged (thinking-off render plus
  `Exact Answer:`), so the slot readout repeats BOLT's and is not a readout here. Greedy, `cache_prompt` false, same
  corpus, same grader (last `Exact Answer:` line, content preferred over reasoning).
- **Paired reference:** `raw/main_BOLT.jsonl` (same file and build; thinking off, `-c 4096`).
- The 20 probe items and 10 controls are part of M1 and are not excluded; the probe was greedy too, so for them this
  arm should reproduce it (checked and reported).

## Readouts and predictions (`analyze_bolt_think.py`, committed with this file; paired bootstrap, 10,000, seed 20261018)

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **Thinking raises refusal of invented items** | U refusal ON - OFF >= +0.15, CI lower > 0 | 0.75 |
| P2 | **Thinking leaves knowledge roughly unchanged** | H acc ON - OFF within +/-0.07 | 0.6 |
| P3 | **Thinking does not make it timid** | H abstained ON <= 0.05 | 0.7 |
| P4 | **Answers finish** | TRUNCATED <= 5 % at 8,192 tokens | 0.8 |
| P5 | **Refusals come from longer thinking** | among invented items with thinking on, median reasoning length of ABSTAINED > WRONG (reasoning chars / 4; `run_main.py` rows do not record usage) | 0.75 |

Reported without prediction: E acc ON - OFF; the probe items' agreement with the probe; per-template refusal (cap,
nov, ope, uni).

## Stop rules

As `PREREG_BOLT.md`, except that `reasoning` is expected to be non-empty here; a row whose reasoning is empty is
reported. A server death resumes on a fresh server, recorded.
