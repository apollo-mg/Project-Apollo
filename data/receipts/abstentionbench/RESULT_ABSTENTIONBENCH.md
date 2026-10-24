# RESULT: AbstentionBench reproduces on llama.cpp, and its judge leans toward the answer key it is shown

**Prereg:** `PREREG_ABSTENTIONBENCH.md` (`dca39c9f`), Addendum 1 (`9df4729a`, registered after the gate and before any
norefs verdict or adjudication label). **Arm 1:** Llama 3.1 8B Instruct Q8_0 as subject and judge, RX 9070 XT,
upstream llama.cpp `f74e2fa` (ROCm), Meta's fast subset (2,004 items, 21 datasets, 870 should-abstain), Meta's sampling
(T 0.8, top_p 0.95, 4,000 tokens, no system prompt). 0 request errors and 0 unparseable judge verdicts in any pass.

## Findings

1. **Gate G passes.** Over the 18 datasets Meta reports unsplit, our F1 (exact judge) is a mean 0.069 from theirs
   (limit 0.10), Spearman 0.922 (limit 0.6). We run slightly high: signed mean +0.034, higher on 12 of 18.
2. **The answer key moves one verdict in ten toward itself (J1-J3 hold).** With the `[GROUND TRUTH ABSTENTION LABEL]`
   line removed, 204 of 2,004 verdicts change (0.102), 198 of them toward the label, symmetric in direction (100
   should-answer items move to "not an abstention", 98 should-abstain items to "abstention"). Mean F1 over datasets:
   exact 0.685, blind 0.566, norefs 0.573.
3. **Where the judges disagree, the answer key does not make the judge more accurate (A1 holds, narrowly).** A blinded
   read of 77 disagreement items (question and answer only) agreed with the reference-free judge on 0.636 [0.53, 0.74],
   Meta's exact judge on 0.571 [0.46, 0.68], and the references-without-label judge on 0.416 [0.31, 0.53]. Paired,
   norefs right where exact is wrong on 30 items, the reverse on 25: not a significant gap. The asymmetry is in the
   should-abstain stratum: there the exact judge called 36 of 40 answers abstentions, and the adjudicator agreed on 18 of
   those 36. Half of the key-driven "abstained" verdicts were answers. Exact 0.475 vs norefs 0.625 in that stratum.
4. **The empty-reference leak turned out not to matter (N1 fails).** On 12 datasets an empty reference list marks
   exactly the should-abstain items, so "blind" could still read the key. Removing the references as well changed mean
   F1 by -0.007 (predicted >= +0.03 the other way). N2 holds only by 0.009 (ref-leaky -0.003 vs other -0.012), which is
   noise. The references hurt instead: the blind judge is the worst of the three, mostly by calling answers to
   answerable questions abstentions (0.243 agreement on should-answer disagreements).
5. **Controls (A2 holds, at the bar).** On 20 unanimous items the adjudicator agreed with all three judges on 18 (0.90).

**Decision rule fired:** the primary judge for later arms is **norefs**. Exact does not beat it by 0.10; it trails it.
Exact is reported second, for comparability with Meta's tables.

## What it means

Meta's published F1 scores carry a label-following component. On this subject the label line is worth about +0.11 mean
F1, and the judge it produces is no more accurate where it matters. It is not that the reference-free judge is correct:
it agrees with a careful reading on only ~64 % of the hard items. The point is that it is the less biased instrument
for comparing models, because a key-reading judge pulls every arm toward the key and compresses the differences
between them. We have not checked how Meta validated their judge, or whether the label was in the prompt when they
did. Answer that before any public note.

## Gate rows (F1, abstention as positive class, exact judge)

| dataset | ours | Meta | diff |
|---|---|---|---|
| ALCUNA | 0.866 | 0.810 | +0.056 |
| BB/Disambiguate | 0.520 | 0.468 | +0.052 |
| BB/Known unknowns | 0.958 | 0.958 | -0.000 |
| BBQ | 0.911 | 0.851 | +0.060 |
| FalseQA | 0.637 | 0.607 | +0.030 |
| GPQA-Diamond | 0.687 | 0.689 | -0.002 |
| GSM8K | 0.966 | 0.961 | +0.005 |
| MMLU History | 0.645 | 0.536 | +0.109 |
| MMLU Math | 0.881 | 0.780 | +0.101 |
| MediQ | 0.327 | 0.235 | +0.092 |
| MoralChoice | 0.500 | 0.402 | +0.098 |
| Musique | 0.902 | 0.824 | +0.078 |
| QAQA | 0.518 | 0.534 | -0.016 |
| QASPER | 0.519 | 0.404 | +0.115 |
| SQuAD 2.0 | 0.851 | 0.725 | +0.126 |
| SituatedQA/Geo | 0.455 | 0.631 | -0.176 |
| UMWP | 0.723 | 0.761 | -0.038 |
| WorldSense | 0.400 | 0.485 | -0.085 |

Likely sources of the positive lean: a Q8_0 GGUF subject and judge on llama.cpp vs Meta's setup, our 100-item fast
subset vs their larger evaluation sets, and T 0.8 sampling.

## Adjudication: robustness

Agreement on disagreement items under alternative label choices (exact / blind / norefs): as frozen 0.571 / 0.416 /
0.636; the three revised items set back to unclear 0.573 / 0.400 / 0.640, or to "not an abstention" 0.571 / 0.390 /
0.636; the 3 unclear items all counted as abstentions 0.550 / 0.412 / 0.637, or all as not 0.588 / 0.425 / 0.625. The
ordering never changes.

## Deviations and limits

- **Deviation 1** (registered in Addendum 1): attempt 1 was killed by systemd-oomd at 411 rows because the server's
  host-RAM prompt cache filled. Rerun from row 1 with `--cache-ram 0`; the 411 rows were discarded.
- **Deviation 2 (display, decided before any label):** in the adjudication sheet, questions over 3,000 characters were
  shown as their first 1,800 and last 1,000 characters, the same rule the prereg set for answers. QASPER and ALCUNA
  prompts carry whole papers and taxon records; whether an answer abstains does not depend on the omitted middle.
- **Label revisions before unblinding:** three items first marked unclear (an explicit "difficult to say" or "ambiguous"
  followed by a hedged pick) were set to "abstained" under Meta's "sufficiently expressing caveats or uncertainty". The
  labels file was hashed (sha256 `f43603e9...`) before the key was opened. 3 of 100 items stay unclear.
- **The adjudicator is an LLM:** Claude Opus 5.5, the model that designed the test and registered A1. It worked blinded
  to label, references, verdicts and dataset, but it is not a human panel. The borderline class is "answered, with a
  caveat", and Meta's definition leaves "sufficiently" to the reader.
- One subject model so far; n = 77 disagreement items gives wide intervals.

## Files

`verdicts_LLAMA8.csv` (all 2,004 items: label and three verdicts, no text), `adjudication_LLAMA8.csv` (the 100 sampled
items, no text), `RESULT_LLAMA8.json`, `RESULT_LLAMA8_adjudication.json`, scripts. Responses, judge replies and the
adjudication sheet stay local (`raw/`): they hold item text, and GPQA's terms forbid publishing its examples.
