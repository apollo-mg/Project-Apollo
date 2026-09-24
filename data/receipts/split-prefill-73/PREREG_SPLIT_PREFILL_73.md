# Pre-registration -- .73 split mode at depth: prefill/decode vs context depth, -np 4 under -sm layer, and the VBR floor in llama-server

**2026-09-24, before any run.** Motivation: Hermes compaction on .73 costs two prefills (the summarizer reading the
compressed span, then the next turn re-reading everything kept). Every compaction-regime estimate so far scales from
one 3k-token sample (149 tok/s). Mark also recalls that tensor split buys decode but costs prefill, and wants `-np 4`
tried under `-sm layer` (the `-np 4 -sm tensor` config aborted today, `vbr-artifact-store/INCIDENT_73_NP4_TENSOR_CAPTURE_ABORT.md`).

**Prior art checked:** `ledger_precheck.py "prefill tensor split layer split 73 depth"` -> receipts found:
- `qwen38-splitmode/RESULT_P100_SM_TENSOR.md` (08-14): `-sm tensor` 1.62x over one P100, `-sm layer` inert. End-to-end
  completion rates only; it says prompt processing was not separated from generation.
- `fleet-throughput` notes (.194): prefill scaled better than decode across 2 -> 4 GPUs under tensor split.
- INDEX L119/L122: `-sm tensor` broke prompt-cache reuse / artifact-store binding on older builds.

**What this adds:** prefill and decode *at depth* per split mode on the daily-driver config, the `-np 4` crash retest
under `-sm layer`, and whether the VBR floor is sticky in llama-server (AFM-46 was seen in llama-perplexity).

## Instrument

- `.73` (2x P100, 1063 MHz / 150 W), buun `08826ad6e` (`build_sm60_0920`), the daily-driver flags from the wake
  proxy (`Qwen3.8-27B-Q6_K` + mmproj, `-c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -fa on
  --spec-type draft-mtp --draft-max 3 --kv-unified`), changing only `-sm` and `-np`. Wake proxy stopped for the
  duration (no relaunch, no suspend).
- Fresh server per leg; one discarded warmup request; readiness = a completion that returns tokens.
- `/completion` with raw token ids, `cache_prompt: false`, `n_predict 256`, `ignore_eos`, temperature 0.
  Disjoint slices of `quant-hesitation/corpus_reasoning.txt`: **128k** `[0:131072]`, **64k** `[131072:196608]`,
  **16k** `[196608:212992]`, then a **2k** `[212992:215040]` probe.
- Recorded: server `timings` (prompt and predicted tok/s, draft stats), `GET /slots` `kv_bpv` before/after each
  request and polled every 5 s during it.

**Legs:** T = `-sm tensor -np 1` (as served), L = `-sm layer -np 1`, L4 = `-sm layer -np 4` (crash + reuse matrix:
turn 1, turn 2, a title-style side request, turn 3, then a side request concurrent with turn 4).

## Predictions

| # | claim | conf |
|---|---|---:|
| P1 | T prefill tok/s > L prefill tok/s at every depth (against Mark's recollection) | 0.60 |
| P2 | T decode tok/s > L decode tok/s at every depth (prior art 1.62x end-to-end) | 0.80 |
| P3 | prefill tok/s falls with depth in both legs (16k > 64k > 128k average rate) | 0.85 |
| P4 | L4 survives the reuse matrix and the concurrent side request (no abort) | 0.70 |
| P5 | L4 turn 3 reuses the conversation prefix after the side request (cache_n > 0) | 0.60 |
| P6 | **sticky floor:** after the 128k request, the fresh 2k probe still reports the degraded `kv_bpv` (not 16) | 0.50 |

**Reading:** P1 false means Mark's recollection holds and the compaction summarizer belongs on a layer-split or
different box. P6 true gives buun a llama-server repro of the floor bug. The compaction-cost table is recomputed from
the measured prefill curve either way.

## Not established by design

One model, one run per depth per leg (the within-leg depth sweep is the replication). Temperature 0 with MTP: decode
rates include draft acceptance, which is text-dependent.
