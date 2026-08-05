# Pulsar ↔ llama.cpp logit agreement on sm_60 — 47/48 top-1, no evidence of a numerics defect

**Stage 2 of the pulsar external-numerics panel** (stage 1: `TOKENIZER_PARITY_SM60.md`, 8/8).
Date 2026-08-03. Node `.73`, 2× Tesla P100-PCIE-16GB (**sm_60 — below pulsar's stated sm_61
dp4a floor**). Model `Hermes3.6-35B-A3B-Uncensored-Genesis-V6-APEX.gguf` (25.69 GB), **the same
GGUF file** fed to both engines.

## Method

- **llama.cpp** `~/llama_stock_ref/build/bin/llama-server`, both GPUs (`-sm layer`; 25.7 GB does
  not fit one 16 GB card), `/completion` with `temperature 0`, `top_k 1`, `n_probs 5`,
  `n_predict 48`, `cache_prompt false`. Yields a greedy trajectory **plus** the top-5 distribution
  at each step.
- **pulsar** `a7fc493` + sm_60 port, single GPU, `--tokens <exact ids> --teacher-force --temp 0`,
  scored on the *identical* 58-token sequence (10 prompt + 48 generated).
- **Alignment:** llama `completion_probabilities[j]` ↔ pulsar `pos = P-1+j`.
- **Normalisation:** llama emits log-softmax, pulsar emits raw logits, and a top-5 slice cannot be
  normalised. Softmax differs from logits by one additive constant `log Z`, so
  `logprob[i]-logprob[0] == logit[i]-logit[0]` **exactly** — all magnitude comparison is done on
  gaps relative to top-1.
- Prompt is plain ASCII with no backslash, per the stage-1 finding that `llama-tokenize` applies
  `--escape` by default.

## Result

| metric | value |
|---|---|
| positions compared | 48 |
| **top-1 agreement** | **47/48 = 97.92%** |
| top-5 exact set match | 41/48 = 85.42% |
| gap Δ (n=233 shared tokens) | mean **0.0886**, median 0.0536, max 0.6210 |

**Pre-registered verdict: PASS** (thresholds fixed before any output was inspected — PASS ≥95%
top-1 *and* mean |Δgap| <0.15; FAIL <90% or >0.50).

The one mismatch is a near-tie, not a disagreement:

```
j=37 pos=46  llama=55026  pulsar=39300  margin_llama=0.1732  margin_pulsar=0.0287
```

Both engines were nearly indifferent between two candidates; pulsar's own top-1/top-2 margin there
was 0.03. A structural fault would not concentrate itself in the single lowest-confidence position.

## ⚠️ What this does NOT establish — the confound

**This is not a clean test of the `__dp4a` polyfill.** Pulsar does not compute on the same weights
llama.cpp does: it uploads `MatW`/`DenseKq` tensors as raw K-quant but **requantises the remaining
K-quants and the embedding table to `q8_0`** (`lib.rs` ~2960, "~1.9× for Q4_K"). It also builds
with `--use_fast_math` globally, and ran single-GPU here against llama.cpp's two-GPU layer split.

So the residual divergence has at least four candidate sources — requantisation, fast-math,
different kernels, different split — and this experiment separates none of them. What it *does*
establish is an **upper bound**: whatever the sm_60 polyfill is doing, total cross-engine
divergence stays at 2% top-1 and ~0.05 median gap. A broken integer dot-product would not survive
inside that bound.

⚠️ **Threshold-anchor caveat.** The pre-registered numbers borrowed anchors from this fleet's
sm_60 FAST_FP16 work (broken = same-top 96.5%, fixed = 99.9%). That was **llama.cpp vs llama.cpp**
with one flag changed — same weights, same kernels. Those anchors do not transfer cleanly to a
cross-engine comparison, where 97.92% is unremarkable. The PASS stands on its pre-registration,
but do not read "97.92% vs 99.9%" as a deficit.

## The experiment that WOULD isolate dp4a

Same engine, same requantisation, same fast-math — vary only the instruction:
**pulsar on sm_75 (the 1660 Ti on `.76`, which has hardware `dp4a`) vs pulsar on sm_60 (emulated).**
Identical `--tokens --teacher-force` sequence, compare top-1 and gaps. Any divergence there is the
polyfill and nothing else. Constraint: the 1660 Ti has 6 GB, so this needs a small model or relies
on pulsar's streaming tier.

## Limits

- One model, one 58-token sequence, one prompt. Not a broad sweep.
- Greedy trajectory only — no coverage of low-probability regions of the distribution.
- `n_probs 5` truncates to top-5; tail divergence is invisible.
- Says nothing about the multi-GPU path (see `Pulsar_Engine_Findings.md` — 75× remote-tier penalty).

## Provenance

- `.73:~/stage2/` — `llama_resp.json`, `prompt_ids.txt`, `stage2_result.json`, `stage2a.log`, `server.log`
- `.73:~/stage2a_llama.sh`, `.73:~/stage2b_compare.py`
- Related: `TOKENIZER_PARITY_SM60.md`, `../../Apollo Docs/Pulsar_Engine_Findings.md`
