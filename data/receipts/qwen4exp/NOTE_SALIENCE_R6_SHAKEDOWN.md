# Shakedown — Salience-27B-R6: the reasoning-economy claim shows a signal; the MTP claim is untestable from this GGUF

**2026-09-14 17:25–17:34, `.194`**, two P100s. **Screening, not a scored test** — no prereg, n=2 prompts, no
accuracy check. Run to decide whether this model earns a real prereg. bartowski's
`vectionlabs_Salience-27B-R6-Q6_K.gguf`, **hash-verified** `c97bd0ec…` against the published sha256.
Flags byte-identical to today's stock dense-path arm (`RESULT_SM60_DENSE_PATH.md`) so the throughput
numbers are directly comparable.

## Mechanical health — no surprises

| | Salience R6 Q6_K | stock Qwen3.8-27B Q6_K | note |
|---|---|---|---|
| peak VRAM | 22,864 MiB | 22,516 MiB | bartowski's recipe is heavier (22.22 vs 21.3 GiB) |
| prefill @ `-ub 512` | 104.0 tok/s | **106.3** (measured today) | −2.2%, tracks the extra bytes |
| decode | 8.10 tok/s | **7.81** (`RESULT_EXL3_SM60_INFERENCE.md`) | +3.7% |
| coherence | PASS | — | |

A same-architecture finetune should not move throughput, and it does not.

## 1. The MTP claim cannot be tested from this GGUF

The model card's headline improvement is **draft acceptance**. The head is genuinely present — metadata
declares `qwen35.nextn_predict_layers = 1`, `n_layer = 64`, and bartowski's layout forces `^blk\.64\.=q4_0`
(the single `q4_0` rule in a file of 499, matching how unsloth ships Qwen3.8's MTP). **But llama.cpp
discards it:**

```
W model has unused tensor blk.64.attn_q.weight (size = 35389440 bytes) -- ignoring
W model has unused tensor blk.64.attn_k.weight ... -- ignoring
W model has unused tensor blk.64.attn_output.weight ... -- ignoring
```

llama.cpp expects MTP as a **separate draft GGUF** (`mtp-*.gguf`), not embedded in the main file. So ~59 MB
of MTP tensors ship and are thrown away on every load, and **R6's central claim is unmeasurable here** — not
because the model lacks the capability, but because the conversion put it where the runtime will not look.

**Worth reporting to bartowski:** extracting `blk.64` into a separate `mtp-…-Q4_0.gguf` would make the
model's headline feature usable. The tensors are already correctly quantised for it.

## 2. The reasoning-economy claim shows a real signal

Same two prompts, both models, **template default — no `--reasoning-effort` set**, which is the condition
R6's claim is actually about ("R5 made it a configuration choice; R6 moves it into the weights").

| prompt | Salience tokens | Salience reasoning chars | stock tokens | stock reasoning chars |
|---|---|---|---|---|
| easy (*what does `ls -v` do*) | 137 | 360 | 122 | 392 |
| **hard** (*lock-ordering deadlock*) | **721** | **593** | **751** | **1078** |

**On the hard prompt: a comparably-sized answer (−4% tokens) using 45% less chain-of-thought.** Reasoning
scaling from easy to hard is **1.65× for Salience against 2.75× for stock**.

That is the direction the claim predicts, at the condition the claim specifies.

## Verdict: worth a deep test, on one axis only

**Test the economy claim. Skip the MTP claim until a draft GGUF exists.**

The instrument already exists and is validated: **test 11's HumanEval+ harness records pass rate *and* mean
output tokens** (`RESULT_EXL3_USABLE.md`), and the paired sign test is committed in
`tools/score_exl3_usable.py`. Base-model numbers exist for comparison.

**The deep test must hold accuracy constant**, because that is exactly what this shakedown cannot do:
*"reasons efficiently"* and *"stops too early"* produce identical token counts. The Puzzle/Laguna panel
already found a case where a gap was **a stopping-rule failure, not an answering failure**
([[puzzle-humanevalplus-run-2026-07-23]]) — the same confusion, previously measured on this fleet.

## Limits

- **n = 2 prompts, no correctness check, one quant, one node.** A signal, not a result.
- Reasoning *chars* is a proxy for reasoning *tokens*; the harness measures tokens properly.
- bartowski's Q6_K recipe differs from unsloth's — the throughput comparison is against stock at a
  *nominally* equal quant, not a byte-equal one ([[gguf-label-is-not-a-spec]]).
- Both models were run with `--jinja` and their own shipped templates, which differ.

Artifacts: `salience/` — `shake.log`, `fetch.log`.
