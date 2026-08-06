# Magnitude of the VBR slot bug — MoE vs dense

**2026-07-27.** `.73`, dual Tesla P100 (sm_60), 1063 MHz / 150 W, `buun_vbr`,
`-ctk vbr -ctv vbr --vbr-floor 6.125 -np 2 --kv-unified -sm tensor -ts 1,1 -c 32768`.
`/completion`, raw prompts, `temperature 0`, `top_k 1`, `top_p 1.0`, `seed 1234`,
`n_predict 400`, **`cache_prompt=false`** (prompts differ and interleave, so a warm cache
would be an uncontrolled variable — see `PREFIX_CACHE_CHANGES_OUTPUT.md`).

12 prompts, each run on slot 0 then slot 1, sequentially, no concurrency. Slot 0 is the
first-exercised slot and therefore the f16-exact reference.

## Headline: the bug is architecture-independent and substantial on both

| | MoE (`Hermes3.6-35B-A3B` Genesis V5 APEX) | Dense (`Qwen3.6-27B` Q6_K) |
|---|---|---|
| divergence rate | **11 / 12 (91.7 %)** | **10 / 12 (83.3 %)** |
| median normalized first-divergence | 0.211 | 0.337 |
| median similarity (all prompts) | 0.526 | 0.730 |
| **worst single case** | 0.149 | **0.035** |

Each slot remains perfectly reproducible *within itself* (verified 2/2 on dense, 3/3 on MoE
earlier). The two slots disagree with each other.

**This is not a cosmetic difference.** An earlier characterisation — "a semantically
equivalent phrasing swap at char 392" — was based on a single prompt and is **not
representative**. At n=12 the median similarity is 0.53 (MoE) / 0.73 (dense), and the worst
cases (0.149 MoE, **0.035** dense) are different answers, not different wording. On dense,
one prompt diverged at **character 2**.

Users cannot see or choose which slot serves them.

## Pre-registered prediction: NOT CONFIRMED

Logged before the run: *"MoE should diverge earlier, more frequently, and more abruptly,
because the router picks top-8 of 256 experts and a near-tie flips which weights run — a
discrete change, versus a smooth logit shift in dense."* Confidence ~70 %.

**Direction is consistent; the effect is not statistically distinguishable at this n.**

| metric | MoE | dense | Mann-Whitney |
|---|---|---|---|
| normalized first-divergence | 0.211 | 0.337 | U=69.0, z=0.99, **p=0.324** |
| similarity | 0.526 | 0.730 | U=62.0, z=−0.58, **p=0.564** |
| divergence rate | 11/12 | 10/12 | one prompt apart — no information |

Both point the predicted way and neither is significant. **Scored as: direction right,
magnitude not established.** Anyone citing "MoE amplifies numerical perturbation" from this
data would be over-reading it.

The single most striking sub-result cuts *against* the amplification story: **dense's worst
case (0.035) is worse than MoE's worst case (0.149).** Dense can be hit at least as hard.

## Which prompts are affected looks arbitrary

Prompt 8 (floating-point associativity) was the **only** byte-identical prompt on MoE, and
the **worst** divergence on dense (0.035). Prompts 4 and 7 were identical on dense but
diverged on MoE. So susceptibility is prompt- **and** model-specific with no visible pattern —
consistent with "a near-tie flips somewhere, and where the first near-tie falls is arbitrary."

## Confounds — this is not a clean architecture isolation

- The two models differ in **quantization** (APEX mixed-precision vs Q6_K), **fine-tuning**
  (Genesis V5 uncensored tune vs stock), and **parameter count** (35B-A3B vs 27B) — not only
  dense-vs-MoE.
- Dense generated longer outputs at the same token budget (~1,800 chars vs ~1,900 for MoE
  at 400 tokens, with different tokenizer efficiency), which shifts normalized positions.
- n=12 per arm. Underpowered for anything but a large effect.
- A clean test needs a **stock MoE at matched quant** against a **stock dense at matched
  quant**, same family. Not available on `.73`.

## What this is good for

The bug is a **controlled, reproducible numerical perturbation** that can be switched on by
choosing a slot — rare and useful. Once buun fixes it, this apparatus stays valid as a way to
inject a known perturbation and measure architectural sensitivity, given matched models.

For buun right now: **the bug substantially changes output on both architectures, on ~85–90 %
of prompts, sometimes completely.** That answers his "quality issue or not" question in the
direction he was worried about.

Apparatus: `HermesAgent-20/slot_divergence.py`. Raw per-prompt data:
`HermesAgent-20/slot_divergence/{moe,dense}-vbr.json`.
