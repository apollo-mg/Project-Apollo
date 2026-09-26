# Pre-registration -- quant-abstention PILOT: does the answer-slot readout predict behaviour, and does thinking-off show the effect?

**2026-09-26, before any corpus item is scored.** Campaign design: `DESIGN.md`. This pilot decides the main
campaign's readout, regime and size. It makes no claim about methods.

**Prior art checked:** `ledger_precheck.py "abstention calibration quantization ladder bpw unanswerable"` ->
receipts found:
- L148 `viability/RESULT_AD_QUANT_LADDER.md`: an AD ladder, medium effort, 8 items x 3 reps. IQ2_XS was timid
  (20/24 answerable, 24/24 abstained). The CAL-U3 "1906" belief erased, not corrected.
- L58/L59/L82: `xhigh` is the abstention outlier.
- FAILURE_MODES AFM-22: unanswerable-only sets reward timidity, and orthographic tells test a different thing.
- `viability/A1_MEASUREMENT_CORPUS_SPEC.md` (not built; three arms after its 09-07 amendment) and its sizing
  results `RESULT_A1_SIZING_DISCORDANCE.md` / `RESULT_A1_SIZING_MEDIUM.md`.

**What this adds:**
- A continuous answer-slot readout, validated against behaviour per quant.
- Thinking-off as the regime.
- A corpus built from Wikidata with model-independent obscurity.
- Sizing for a method-ladder campaign at matched bytes.

## Corpus P0 (built before any model sees it; `corpus/P0.jsonl`)

- **40 E** (high sitelinks), **40 H** (low sitelinks), **40 U** (plausible fakes). Same templates across arms.
- **Every E/H gold:** Wikidata QID + property, recorded.
- **Every U item:** no exact-label Wikidata entity, plus a no-hit exact-phrase web search, both recorded.
- **Mark spot-checks 12 items** (4 per arm, drawn by a seeded RNG) before the run; any failure means the arm's
  construction is reviewed.
- **Prompt:** the CAL tier prompt (`viability/fixture_v0_beta.json` `tier_cal.prompt`, which offers "UNKNOWN"),
  thinking off, one user message.

## Model arms (one instrument)

| arm | file | why |
|---|---|---|
| C | Q8_0 | ceiling |
| M | AD IQ3_XXS | mid PTQ rung |
| L | AD IQ2_XS | low PTQ rung (the "timid" cell on L148) |
| B | Bonsai 2 PQ2_0 | the "confident" contrast. The readout must be valid for that failure mode too |

- **Box:** `.194`, buun `0b2789f23` built sm_60 (the current `.73` daily-driver commit), 2 GPUs.
- **Settings:** `-sm layer`, `-ngl 99`, `-c 4096`, `-ctk f16 -ctv f16` (explicit; the KV type verified in the log),
  `-np 1`, MTP off, `cache_prompt: false`.
- **Load hygiene:** a server restart per arm, and one discarded warm-up request.
- **Hashes:** the sha256 of every model file is recorded at run time.

## Readouts

- **R-slot:** `P_abs` = P(" UNKNOWN") + P(" Unknown") + P(" unknown") at the next token after the rendered prompt
  (thinking off) + `Exact Answer:`, from the full top-k (`n_probs 50`). Missing variants count as 0.
- **R-gen:** greedy, thinking off, `max_tokens 48`. Graded as CORRECT / WRONG / ABSTAINED(unanswerable) /
  ABSTAINED(answerable).
  - The grader is exact match after normalization (case, punctuation, a leading "The").
  - Years must match exactly.
  - Names match if the gold's Wikidata label or any of its aliases appears as the answer.

## Pilot questions and registered decisions

| # | question | test | decision |
|---|---|---|---|
| P1 | Is R-slot valid? | per arm, agreement between (`P_abs` > 0.5) and (R-gen ABSTAINED) over all 120 items | if **>= 85 % in every arm**, R-slot is the main campaign's primary readout. Otherwise R-gen is primary, and R-slot is descriptive (with the failing arms named) |
| P2 | Does thinking-off show the phenomenon? | for L and B vs C: the differences in R-gen H-arm CORRECT, and in U-arm abstention, with bootstrap 95 % CIs over items | if **no arm differs from C on any metric** (all CIs include 0), thinking-off cannot carry the campaign, and the main regime is medium thinking |
| P3 | Corpus in range? | at C: E-arm CORRECT >= 85 %; H-arm CORRECT in [25 %, 75 %] | if H is out of range, the sitelink band is moved (a construction change, not item-picking on a model), and P0 is re-drawn |
| P4 | Sizing | the measured item-level discordance (R-gen) and SD (R-slot) for C vs L | the main N is set from these, and registered in the main prereg |

**Predictions** (to be checked, not gating):

| # | claim | conf |
|---|---|---:|
| Q1 | R-slot agreement >= 85 % in C and M | 0.6 |
| Q2 | L is **timid** at thinking-off: H CORRECT lower than C, and mean `P_abs` on answerable higher than C | 0.5 |
| Q3 | B is **confident**: U-arm abstention lower than C, with mean `P_abs` on answerable not higher than C | 0.5 |
| Q4 | Discrimination (AUROC, U vs E+H) at C >= 0.85 | 0.6 |

## Not established by design

- 40 items per arm, one model, one PTQ packager (AD) plus Bonsai.
- Thinking-off only.
- Nothing here compares methods: that is the main campaign's job.

## Deviation 1 -- corpus construction, before any model saw an item (2026-09-26)

A dry run of the P0 builder showed the capital template's H pool (sitelinks 3-8) could not supply 10 clean items:
- **28 of 42 leak the answer.** Most are Mali regions, Algerian provinces and Lithuanian city municipalities named
  after their capitals.
- **Most of the rest are anomalies:** historical uyezds, former provinces, electoral constituencies, NUTS
  statistical regions, and a 3-sitelink duplicate item of the Balearic Islands.

Real administrative regions collect many bot-stub sitelinks, so the low band holds oddities rather than obscure
regions. Mark chose the fix:
- **Capital H band:** 3-20 sitelinks (the other templates stay at 3-8).
- **Two capital-only item checks:**
  - E and H must be current, uncontested administrative regions.
  - An H item's exact name must not belong to a famous entity (40+ sitelinks).

Construction rules added in the same pass, applied without looking at any model:
- **Rows:** one per (item, answer), so the opera UNION's double tags are no longer read as two answers.
- **Leak filter:** the answer must not be readable in the item or country label.
- **Year golds** need year precision.
- **Parenthetical labels** are dropped.
- **Articles:** added by one rule for real and fake items alike.
- **Fake names:** 3 web passes shared an exact Wikidata label with small real places and were replaced (fakes.py
  rule wd).

The full rules are in the `corpus/build_p0.py` docstring. Every drop and redraw is in `corpus/P0_build.json`.
