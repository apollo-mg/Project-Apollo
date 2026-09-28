# Pre-registration: does Swift-Bonsai-2 fib less than Bonsai 2?

**Registered 2026-09-28, before any Swift-Bonsai row.** Mark: "Wonder if it fibs any less lol."

**Models:** both in the same PQ2_0 packing.
- `ukisai/Swift-Bonsai-2-GGUF`, `Swift-Bonsai-2-PQ2_0.gguf`, sha256 `5912bb73…33d5` (verified at fetch).
- The base, `prism-ml/Ternary-Bonsai-2-27B-gguf`, `…PQ2_0.gguf`, sha256 `3907dc16…2ec1` (fetched 09-19).
- **Both are 7,206,168,928 bytes, but different.** 101.6 MB of bytes differ, spread over 681 of 851 tensors in all 64
  layers (every weight-matrix kind plus the norms). Swift is a light correction across the whole network, merged
  back into ternary. Its card claims "39.8 % fewer thinking tokens" at "0.19 % higher" accuracy, from fine-tuning
  against reasoning-marker tokens.

**Prior art checked:**
- `viability/RESULT_SWIFT_BREVITY_TAX.md` (Swift on Qwen3.8-27B): -26 % thinking on false premises, unanswerable
  failures 6/24 vs 4/24 (p = 0.72, a trend);
- `marker-penalty/RESULT_MARKER_PENALTY_BONSAI.md`: an inference-time marker penalty on Bonsai 2 trims the tail;
  answers unchanged;
- `quant-abstention/RESULT_MAIN.md`: base Bonsai 2 on M1, at .194;
- `bonsai-hip/RESULT_BONSAI_HIP_VALIDATION.md`: prism `9a9394a` build_hip decodes Bonsai 2 correctly on gfx1201.

**What this adds:** Swift's weight-level version of the marker penalty, on the model family where the penalty worked
at inference time. Base and Swift share one card, one build and one harness, so the only variable is the Swift
weights.

## Instrument

- **Hardware and build:** RX 9070 XT, prism `9a9394a89` (`engines/prism_sep/build_hip`).
- **Server:** `-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off`, port 8097.
- **Discipline:** one fresh verified server per model (own log loaded; `/props` names the file), one discarded
  warm-up. Order: base (stage 1 then 2), then Swift (stage 1 then 2).
- **Stage 1, "fibbing" with thinking off:** `quant-abstention/run_main.py` on M1 (240 items: 40 E, 100 H, 100 U),
  temp 0, `--expect-variants` (the Qwen3.8 UNKNOWN ids). Arms BONB9 (base) and SWB9 (Swift).
- **Stage 2, with thinking on:** `run_fixture_structfix.py --tier cal --effort xhigh --sampling card --seed
  1001|1002|1003 --arm A`. The card is Qwen3.8's (the Bonsai 2 base). Output in `swift_bonsai/{BONB9,SWB9}/`.

## Predictions (`analyze_swift_bonsai.py`, committed with this file)

| # | claim | rule | confidence |
|---|---|---|---|
| S1 | **Swift does not fib less (thinking off)** | Swift - base, U refusal: paired 95 % bootstrap CI lower bound <= 0 | 0.7 |
| S2 | **Knowledge unchanged** | Swift - base, H accuracy: 95 % CI includes 0 | 0.7 |
| S3 | **Swift thinks less where premises are false** | CAL unanswerable: Swift median reasoning chars <= 0.8x base | 0.7 |
| S4 | **Thinking less does not buy honesty** | CAL unanswerable ABSTAINED: Swift <= base (of 24) | 0.6 |

Reported without a prediction: NO-STOP counts, CAL answerable, M1 easy accuracy, and forced-slot P(UNKNOWN).

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
