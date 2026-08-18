# Content notes: `turboquant_plus/docs/papers/asymmetric-kv-compression.md`

**2026-08-18.** Fact-check notes for Mark, prompted by his pointer to TheTom's papers
directory. **Not a draft message and not a rebuttal** — the paper is broader than our work
(7 models, 6 backends) and its mechanism may well be right. These are the specific things
that bear on `RESULT_U5F_ALLOCATION.md`, which measured the opposite direction.

## What the paper concludes

*"Compress V maximally, spend bits on K."* Mechanism: K errors perturb the Q·K logits and
**softmax amplifies them exponentially**; V errors pass through the weighted sum **linearly**
and mostly attach to positions with negligible weight. Secondary mechanism, *"quantization
stacking"*: K-cache error compounds **multiplicatively** with *weight* quantization error in
the logit computation, so lossy weights plus lossy K can exceed softmax's tolerance.

## Structural observation: the mirrored pair is absent

The three results tables (Qwen2.5-7B, Llama-3.1-70B, Command-R+ 104B, all Q4_K_M) have this
shape — verbatim K/V columns:

| K | V |
|---|---|
| `q8_0` | `q8_0`, turbo4, turbo3, turbo2 |
| turbo4 | turbo4 |
| turbo3 | turbo3 |
| turbo2 | turbo2 |

**Every asymmetric row has `q8_0` on K. No row anywhere has a low-precision K with a
high-precision V.** So the tables cannot separate *"K deserves the bits"* from *"more total
bits is better"* — the counterfactual was never run. This is the same unequal-budget trap
this project fell into once already (the `kv_bpv: 16.0` VBR run) and the reason `U5f` was
built as a mirrored swap at equal cost.

The paper's framing sentence *"Same total compression budget, opposite quality outcomes"*
appears to compare `q8_0`-K+turbo3-V against turbo3-K+turbo3-V. Those are **12.0 vs 7.0
bits/value** — a 71 % difference, not the same budget. Flagging as *likely wording*, since
this came through a fetched rendering rather than the raw file; worth Mark's eye before it is
repeated anywhere.

## Their own tables contain counterexamples to a universal "spend bits on K"

Using q8_0 = 8.5, turbo4 = 4.125, turbo3 = 3.5, turbo2 = 2.5 bpv. The ordering is robust even
if TheTom's turbo block layouts differ slightly from buun's, because **`q8_0` alone (8.5)
already exceeds turbo4+turbo4 combined (8.25)**.

| model | config | total bpv | PPL |
|---|---|---:|---:|
| Llama-3.1-70B | `q8_0`/turbo2 | 11.00 | 3.568 |
| | **turbo4/turbo4** | **8.25** | **3.461** |
| Command-R+ 104B | `q8_0`/turbo2 | 11.00 | 6.678 |
| | **turbo4/turbo4** | **8.25** | **6.312** |
| | **turbo3/turbo3** | **7.00** | **6.415** |

**Balanced allocation beats K-heavy allocation while spending 25–36 % fewer bits**, in the
paper's own data, on two of its three models. Where V is pushed to turbo2, a rich K does not
rescue it. That is inconsistent with *"spend bits on K"* as a universal rule, though it is
perfectly consistent with the rule holding **near the K floor**.

## The synthesis that fits both datasets

The paper's catastrophes are all **symmetric configs at Q4_K_M weights**: turbo3/turbo3 →
PPL 3,556 on Qwen2.5-7B. And the paper itself says *"Q8_0+ weights? Symmetric turbo works"*
and *"symmetric turbo is not universally broken — Mistral-24B handles it fine."*

That reads as a **threshold on K, not a linear trade**:

- **Below the floor** (K at turbo3/turbo4 *and* 4-bit weights, where stacking bites) → K error
  breaks softmax routing and the result is catastrophic. Here *every* spare bit must go to K,
  and the paper is right.
- **Above the floor** (our regime: K `q4_0` = 4.5 bpv, **Q6_K weights**) → both sides are
  healthy, and the *marginal* bit is worth more on V. `U5f`: 37.7 % better with bits on V at
  equal cost; `U5d`: 31.7 % in a different codec family.

Consistent with our own numbers: turbo3/turbo3 measured R 159.6 and turbo2/turbo2 R 512.6 —
badly degraded but **nowhere near catastrophic**, which is what Q6_K weights would predict on
their stacking mechanism.

**Both can be true.** "K has a floor you must not cross" and "above that floor, spend the
marginal bit on V" are not contradictory claims, and each dataset only probed one regime.

## Four axes that differ, any of which could carry the discrepancy

| | TheTom's paper | our `U5f` |
|---|---|---|
| **weights** | **Q4_K_M** (4-bit) — where stacking bites | **Q6_K** |
| **metric** | PPL (bulk average) | flip rate, KL, margin-weighted R, CVaR95 |
| **depth** | 512-token PPL windows | **136 tokens** |
| **head_dim** | mostly 128 | **256** |

Neither study is depth-resolved, so **depth cannot currently explain the disagreement** —
both are shallow. The paper's own independent validator reports the asymmetric advantage
*growing* with context (K3V2: +0.82 % at 1,742 tokens → +0.35 % at 3,544), which supports a
crossover but is a single observation.

**Weight quantization is the strongest candidate**, because it is the one axis the paper
itself already identifies as decisive.

## The cheap experiment that would settle it

Re-run `U5f`'s four arms on the **same model at Q4_K_M**, then at Q8_0. If the V advantage
shrinks or inverts as weights get lossier, the threshold synthesis is confirmed and both
results stand as regime-specific. **One model, four arms, three weight quants — ~2 h on
`.194`.** Adding a depth axis on top would resolve the h4rm0n1c question in the same sweep.

This is worth more to TheTom than our result alone: it supplies the mirrored-pair test his
tables lack, in a regime his mechanism predicts should behave differently.

## Also in that directory, relevant to open work

`dflash-self-draft-investigation.md` — bears directly on the DFlash-on-Pascal build now
running on `.73` (`BACKLOG S2`). Unread. `why-mse-fails-for-kv-quantization.md` and
`layer-aware-v-compression.md` also look directly on-topic and are unread.
