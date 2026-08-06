# Battle for 16GB — Results (2026-07-18)

**Gemma-4-12B QAT UD-Q4_K_XL (6.72 GB, ~4.3 bpw) vs Ternary-Bonsai-27B Q2_g64 (7.59 GB, 1.71 bpw)**
RX 9070 XT 16GB, stock clocks. Spec: `Lab_Spec_Battle16GB.md` (+ §4b amendment). Suites mirror W3:
IFEval-541 + GSM8K-250 (seed-42 subset, chat endpoint, `--fewshot_as_multiturn`, custom
`gsm8k_b16chat` task with `until:[]` after the stop-string bug), both models trained-default
thinking, equal `max_gen_toks=4096`, greedy. Gemma with MTP (lossless-in-distribution).
Serving configs + receipts: scratchpad `b16/results/` (mirrored per-leg `serving_config_*.txt`).

## Headline

**The ternary 27B wins both quality suites, decisively.**

| | Bonsai 27B ternary | Gemma-4 12B QAT |
|---|---:|---:|
| IFEval prompt-strict | **73.0%** | 64.5% |
| IFEval prompt-loose | **74.9%** | 65.1% |
| GSM8K-250 (chat, fixed) | **94.0%** | 51.6% |
| — empty responses IFEval | 20.3% | 32.3% |
| — empty responses GSM8K | 0.8% | **46.0%** |
| — conditional acc (answered only) IFEval | 91.6% | **95.4%** |
| — conditional acc (answered only) GSM8K | 94.8% | **95.6%** |
| Decode t/s (this rig) | 46.5 | **110–143 (MTP)** |
| IFEval wall time | 8.5 h | **3.5 h** |
| GSM8K-250 wall time | 3.1 h | **1.3 h** |

## The mechanism (the real finding)

Neither model loses on *ability* — conditional-on-answering they're both ~92–96%. The battle
was decided by **answer-delivery discipline under thinking templates**:

- **Bonsai** fails by *over-thinking past the budget* (IFEval empties are confirmed 4096-cap
  deaths; server log receipts). On math it converges: 0.8% empty. 1 loop-suspect in 791
  prompts — no 2-bit-drunk pathology at 1.71 bpw.
- **Gemma** fails by *thinking, then going silent* — zero budget-cap hits in the entire v2
  run; she closes reasoning and EOSes without emitting an answer. 32% of IFEval, 46% of
  GSM8K-chat. Hypothesis (unproven): interaction between her think-trained template and
  no-think fewshot exemplar turns — same failure family as the P100 Gemma think-closure
  patch. Follow-up candidate: rerun one Gemma leg with `enable_thinking:false`.

## Invalidated legs (kept for the record)

- **Raw-completions GSM8K is dead for both** (the W1/W3 protocol does not transfer):
  Bonsai puts ~100% first-token mass on `<|im_end|>`; Gemma starts correctly then
  degenerates (infinite zeros / token spam). *The completion API is going extinct one
  model generation at a time.* Cross-campaign raw column: N/A-by-behavior for both.
- v2 gsm8k-chat legs (stock `until: ["Question:"...]` fired inside think blocks) — discarded.

## P-scorecard (predictions logged in spec before results)

- **P-B1′ (0.55, Bonsai wins GSM8K-chat): CONFIRMED** — 94.0 vs 51.6.
- **P-B2 (0.70, Gemma wins IFEval): FALSIFIED** — Bonsai 73.0 vs 64.5. (Reversal #14.)
- **P-B3 (0.97, Gemma sweeps throughput): CONFIRMED** — 2.4–2.6× on every speed metric.
- **P-B4 (0.60, Bonsai >99% finish, zero loops): FALSIFIED as worded** (79.7% IFEval
  finish-with-content) but vindicated on the loop clause (1/791). Failure mode is
  over-thinking, not incoherence.

## Caveats

Single greedy runs, one 250-doc seed, one gen budget (4096), chat-format specifics
load-bearing (see mechanism), MTP nondeterminism on Gemma freeform (lossless-in-dist),
different builds by necessity (PR #25707 HIP vs turboquant ROCm). Quality axes would
tighten with a second seed + an `enable_thinking:false` Gemma arm.

## One-line take

At matched bytes on a 16GB card, 2.25× the parameters through radical quantization beat
gentler quantization of a smaller model on every quality headline — but the throughput
crown (2.4×+, MTP) and the per-answer precision edge stay with Gemma, and the decisive
variable in 2026's thinking-model era is neither bits nor params: it's whether the model
reliably *exits the think block with an answer*.
