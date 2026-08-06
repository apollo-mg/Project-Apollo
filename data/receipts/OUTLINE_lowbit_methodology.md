# Content notes — low-bit quant evaluation piece

**These are notes and verified numbers, not draft prose.** Structure to write from; every
figure below is cited to a receipt on disk and was re-read from the file, not recalled.

Occasion: `unsloth/Kimi-K3-GGUF` discussion #12 ("1-bit Kimi K3 vs Claude Opus 5 vs GPT 5.6"),
2026-07/08. Unsloth ran 1-bit Kimi K3 on 4×B200 at 36 tok/s against a single-prompt aquarium
simulation and compared to Opus 5 / GPT 5.6.

---

## The opening: two people asked for exactly this work, in public

Both quotes are verbatim from that thread. They are the reason the piece has an audience.

**HenryT2:**
> "Great demonstration of how powerful 1 bit can be! BUT... Can you (AND EVERYONE ELSE) do
> multiple runs? All you AI 'reviewers' are doing the equivalent of saying 'draw a cat' into
> image generators and then comparing results. I understand that there's time and cost
> involved, but without multiple generations, comparisons are not indicative of true quality."

**coder543:**
> "I wish Unsloth could partner with Artificial Analysis or Datacurve to run some benchmarks
> across various quants... I find the typical KLD measurements to be an unsatisfying
> alternative, and it would be some great research to see how much quantization degrades
> models across a wide range of benchmarks."

The piece answers both, with data that already exists.

---

## Section 1 — "Do multiple runs" is not a nitpick; K=1 measures nothing here

| claim | number | source |
|---|---|---|
| Score is a lossy hash of output | **33 of 36** same-score groups contained *different* completions; zero were ever byte-identical | `hermesagent20/SUMMARY.md:1034` ("score was a lossy hash of the output") |
| Same config, repeated draws, forked scores | **35/100, 20/70, 20/50** — the signature of a decision fork (near-tie) | `hermesagent20/SUMMARY.md:293` |
| Determinism is per-build, not inherited | Ornith **3/3 byte-identical** 1200-token greedy generations, sha `2769dde8ac13d6b4`; other builds on the same box are not | `HA20_THREE_WAY.md:144`, `HA20_BONSAI_VS_GEMMA.md:161` |
| Temp-0 is not reproducible on `.73` | `-np > 1` introduces variability, **temp 0 included** | `hermesagent20/DETERMINISM_ROOT_CAUSE.md:143` |

**The point to land:** two runs can score identically and share almost no text. So a single
side-by-side render is not weak evidence — it is a draw from a distribution nobody has
characterised. K=1 is an existence proof, never a rate.

**Fresh, in-scope example (2026-08-02):** predicted the f16 control on the RX 580 rig would be
bistable at K=3 (conf 0.55) *because* an earlier receipt recorded two distinct f16 states with
cell order fixed. It came back perfectly stable, 21/21 runs, same SHA per cell.
→ `PR244_GCN_SIGNOFF.md`, P-R4 **FALSIFIED**. Use this as the honesty beat: the discipline
cuts against my own predictions too, and I still don't call that rig deterministic.

---

## Section 2 — the quant ladder coder543 asked for, on a task metric

**NVIDIA-Nemotron-Labs-3-Puzzle-75B-A9B**, HumanEval+ 164 problems, **K=3 (492 samples/cell)**,
temp 0.7 / top_p 0.95 / top_k 20, 4×Tesla P100 @ 1063 MHz / 150 W. Wall clock **~36.4 h**.
Predictions sealed pre-run. → `battle16gb/PUZZLE_LADDER_FA_ON.md`

| cell | pass@1 | pass@3 | non-stop | thinking leak |
|---|---|---|---|---|
| q2_off | **67.5 %** | 89.0 % | 3 | **21.1 %** |
| q2_on | **92.5 %** | 96.3 % | 7 | 3.9 % |
| iq4_off | **91.1 %** | 92.7 % | 0 | **0.0 %** |
| iq4_on | **94.3 %** | 97.6 % | 2 | 0.4 % |

- **Thinking gap: 25.0 pp at Q2_K → 3.3 pp at IQ4-XL.**
- Precision recovers **23.6 pp** of the non-thinking score (67.5 → 91.1) while moving the
  thinking score only **1.8 pp** (92.5 → 94.3).
- **Reasoning tokens and weight precision are substitutes for this model.** Q2-that-thinks
  ≈ IQ4-that-doesn't (92.5 vs 91.1).

**Why this is the answer to "KLD is unsatisfying":** it is a *task* metric across a ladder, and
it shows the thing KLD cannot — that the cost of low bits is partly *purchasable back* with
inference-time compute. That is a deployment-relevant fact, not a distributional one.

---

## Section 3 — the mechanism: low-bit fails at control, not content

This is the piece's actual contribution and the strongest hook to that thread, because a
participant reported the symptom without a name for it.

**Thread evidence (`anuppillai`, on `UD-Q2_K_XL`):** the 2-bit run made *"the glass go away"* —
a dropped requirement in a ten-requirement prompt. That is a constraint-tracking failure, not a
knowledge failure.

**Our measurement of the same class:** → `humaneval-plus/SUMMARY.md:102` ("The gap is a
stopping-rule failure, not an answering failure")

| | Puzzle-75B IQ4-XL | Laguna-S-2.1 Q2_K_XL (ON) | Laguna (OFF) |
|---|---|---|---|
| pass@1 pooled | **93.90 %** (462/492) | **90.85 %** (447/492) | **88.21 %** (434/492) |
| TRUNCATED (16k cap) | **1** | **10** | 0 |
| flaky (1–2 of 3) | 10/164 | 11/164 | **24/164** |
| median out_toks | 542 | **1,945** | 274 |

- Laguna produced **no extractable code on 11/492** samples; Puzzle **1/492**.
- Conditioning on samples that produced code at all, the 3.05-point gap collapses to
  **1.16 pt** or **0.58 pt** depending on how EXEC_TIMEOUT is counted.
- **Majority of the headline gap is failure to stop generating, not wrong answers.**

Corroborating, same family: q2_off leaked reasoning into the answer on **21.1 %** of samples;
iq4_off on **0.0 %** (`PUZZLE_LADDER_FA_ON.md:63`).

**Caveat that must ship with it** (already in the receipt): this does *not* say the 11 wedged
samples would have passed. Forcing termination moved Laguna's WRONG count **30 → 56**.

---

## Section 4 — the hardware angle nobody else has

Unsloth's demo: 4×B200. Ours: four **2016** Tesla P100s (sm_60, 16 GB each).

- **DeepSeek-V4-Flash UD-IQ1_S (~1.6 bpw, 82.5 GB)** loads and generates coherently on 4×P100.
  3 min 12 s load, **2.16 t/s**, gzip 0.469–0.567 (healthy band), CJK leakage 0.
  → `battle16gb/DS4_FLASH_P100_LOAD.md`
- **Every row of HuggingFace's own compatibility widget marks that model incompatible with a
  16 GB card.**
- Prompt caching makes it usable multi-turn: an ~8k-token document re-prefills at ~8.5 min
  per turn uncached vs a small delta cached; prefill measured at **61–83 ms/token at 8k**, not
  the 478 ms/token that a ~30-token prompt implied. → `battle16gb/DS4_PROMPTCACHE_LONGCTX.md`

**Limits that must be stated in the same breath** (from the receipts themselves):
- The DS4 1-bit result is **K=1, two prompts, gzip-only** — "a load probe, not a benchmark. No
  capability claim." Publishing it as evidence that 1-bit *works* would commit the exact error
  Section 1 criticises. Frame it as: it runs at all, on hardware that shouldn't.
- gzip ratio detects **degeneration**, not correctness. "Not degenerate" ≠ "good at 1.6 bpw."
- One quant; IQ1_M (86.9 GB) and above do not fit, so there is no ladder for DS4.

---

## Section 5 — the standard to propose

Not "our numbers are better." The claim is about *method*, and it is cheap to adopt:

1. **K ≥ 3, and publish the spread**, not just the mean. Report per-draw values.
2. **State the sampling used.** From `SAMPLING_ENVELOPE_QWOPUS.md`: running Qwopus-Fusion at
   temp 0 (card recommends 0.85–1.0) produced a **50,040-character** tool argument and a hard
   serving failure; at temp 0.9 / top_p 0.9 the same weights produced **1,335 characters**.
   Same weights, 18.6× wall-clock difference on one tier. **The defensible position is to
   report the sampling, not to standardise on one.**
   — and the honest counterweight, same receipt: on t4_ratelimited the recommended sampling was
   **3.5× slower** (368.3 s / 12 attempts vs 104.3 s / 6). One counter-example kills a
   universal claim.
3. **Log predictions with confidence before the run, score them honestly after.** Include the
   falsified ones. (Every receipt cited here does this.)
4. **Report the instrument's blind spots.** gzip catches degeneration, not fidelity; KLD
   catches distribution shift, not task outcome; pass@1 hides stopping failures until you
   count TRUNCATED separately.

---

## Tone / framing notes

- Lead with the thread's own words. The demand is theirs; the data is the answer.
- Do **not** claim to have settled low-bit quality. Two model families, one benchmark.
- The credibility move is the falsified predictions — P-R4 above, and the Qwopus correction
  where a **timeout of mine hid the failure** and I reported the wrong cause before catching
  it (`scrapebench/QWOPUS_RUNAWAY_ROOT.md`).
- Avoid positioning against Unsloth. Daniel's team shipped the quants everything here runs on;
  the 1-bit DS4 result exists *because* of `unsloth/DeepSeek-V4-Flash-0731-GGUF`. The target is
  the evaluation convention, not the quantiser.

## Verification status

Every number above re-read from its receipt on 2026-08-02. Line references are to files in
`data/receipts/`. The two thread quotes are verbatim from the HF discussion API
(`/api/models/unsloth/Kimi-K3-GGUF/discussions/12`), not from the rendered page summary.
