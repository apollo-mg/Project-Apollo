# Result — the blind panel's 2-bit/4-bit contrast is confounded with drawing complexity

**2026-09-11, post-hoc.** Run while designing a larger panel, on the 32 drawings the blind panel
already used (`MAPPING_SEALED.json`), re-probed with the unchanged `svg_probe.py`.

**This is exploratory and post-hoc.** It was not pre-registered, the features were chosen after
seeing the panel result, and no correction for multiple features was applied. It qualifies
`RESULT_BLIND_ART.md`; it does not overturn it.

## The finding

4-bit drawings are **systematically busier** than 2-bit ones. Medians over the 32 panel drawings
(20 at 2-bit, 12 at 4-bit), two-sided permutation test on the median difference, 20,000 shuffles,
seed 20260911:

| feature | 2-bit | 4-bit | p |
|---|---|---|---|
| **DOM elements** | 41.0 | 53.5 | **0.003** |
| **SVG bytes** | 3,303 | 4,261 | **0.004** |
| ink fraction | 0.128 | 0.157 | 0.060 |
| DOM paths | 15.0 | 12.5 | 0.157 |
| DOM circles | 11.5 | 12.5 | 0.347 |
| components | 3 | 3 | 1.000 |
| structural score | 10 | 10 | 1.000 |

## It is not a revision artifact

Element count by review step — the gap is present in every one, including the first drawing, which
has had no revision pass at all:

| step | 2-bit median | 4-bit median |
|---|---|---|
| p1 (first drawing) | 40.0 (n=6) | 53.0 (n=4) |
| goal2 | 41.5 (n=6) | 55.0 (n=3) |
| goal3 | 43.0 (n=2) | 52.0 (n=1) |
| intent2 | 41.5 (n=6) | 54.5 (n=4) |

Step composition is proportional between the groups, so the panel is not skewed toward revisions on
one side. **Per-step cell counts are tiny (1–6); the per-step rows are descriptive only.** The
claim that survives is the pooled one, plus the observation that no step reverses it.

## Why it matters

**Any "which drawing is better" test on these pairs cannot separate two explanations:**
1. the rater perceives quality that tracks bit depth, or
2. the rater prefers busier drawings, and busier drawings happen to be 4-bit.

This applies to every rater, human or machine. It is not a criticism of the raters; it is a property
of the stimulus set.

- **It qualifies Mark's result.** `RESULT_BLIND_ART.md` reports Mark 21/24 toward 4-bit, p = 0.057.
  That is equally consistent with a preference for detail. The design cannot tell them apart.
- **It does not explain the outside raters.** R1 and R2 both scored 12.5/24, near chance, while the
  complexity gap was available to them too. So complexity is not sufficient to drive a preference —
  only Mark's judgments tracked it.
- **A vision-model panel would likely amplify it.** The cheapest strategy for scoring "better" is to
  prefer the more detailed image, which would reproduce the bit-depth effect without any aesthetic
  judgment at all.

## Consequence for a larger panel

Breaking the confound needs pairs matched on complexity, and the current pool cannot supply them:

| pairing | count |
|---|---|
| all cross-bit pairs | 240 |
| complexity-matched (≤5 elements apart) | 23 |
| inverted (2-bit busier than 4-bit) | 39, but drawn from only **5 distinct** 2-bit drawings |

One of those five is an 84-element 2-bit outlier against a 37–46 spread, so an inverted-pair design
would rest on a handful of images and one outlier. **The pool must be enlarged before recruiting
raters**, which is cheap: about 2–3 minutes of 9070 time per drawing.

## Standing on its own

Independently of the judging, this is a measured property of the ladder: **at matched prompt,
harness and sampling, the 2-bit quants of Qwen3.8-27B emit about 23% fewer SVG elements than the
4-bit quants** (41 vs 53.5 median), and the effect is present before any revision. That is a
different axis from the structural score, which saturated at 10/10 for both.

## Addendum — what each rater was actually answering

**Post-hoc, prompted by Mark's account of his own procedure (2026-09-11):** he graded "what comes
closest to a pelican on a bike", deducting for incomplete frames and bad geometry — deliberately
looking for differences that would follow from capability. The share page asked a different
question:

> **"Which is the better picture of a pelican riding a bicycle?"**
> *Judge each picture as a whole. Some pairs are close; "Too close to call" is a real answer.*

That invites a taste judgment. Two raters answering a taste question and one answering a capability
question is sufficient to produce near-zero agreement without anyone judging badly.

**Decisive cross-bit picks** — pairs whose two drawings differ in bit depth, ties excluded:

| rater | picked the 4-bit drawing |
|---|---|
| Mark | **23/23 (100%)** |
| R1 (JabbaTheDuck) | 16/30 (53%) |
| R2 | 16/29 (55%) |

Mark never once preferred a 2-bit drawing over a 4-bit one when he made a call. This is consistent
with the pre-registered 21/24: that statistic ranks aggregated win rates and counts ties as 0.5,
and Mark tied on four cross-bit pairs (for instance `XAA7`, a 4-bit drawing, tied with four
different 2-bit drawings and beat two more, giving it a 0.444 win rate while never losing to a
2-bit drawing).

**Do not read 23/23 as p = 2⁻²³.** The 23 decisions involve only ten drawings, so they are heavily
dependent — a single strong drawing contributes many comparisons. The pre-registered permutation
test accounts for that structure; a binomial does not.

**What the picks track, by feature** (share of decisive pairs where the rater chose the drawing
scoring higher on that feature):

| rater picks the… | Mark | R1 | R2 |
|---|---|---|---|
| busier drawing (DOM elements) | 36/47 (77%) | 34/62 (55%) | 35/55 (64%) |
| less fragmented (fewer components) | 25/37 (68%) | 35/44 (80%) | 28/43 (65%) |
| higher structural score | 18/19 (95%) | 20/24 (83%) | 20/23 (87%) |
| more ink | 31/46 (67%) | 41/66 (62%) | 24/56 (43%) |

Small denominators, and the structural score saturates at 10/10 for most drawings, so the third row
rests on few pairs.

**Three explanations remain live, and this design separates none of them:**
1. Mark perceives quality that tracks bit depth.
2. Mark prefers busier drawings, and 4-bit drawings are busier.
3. Mark applied a capability rubric while the other two applied the taste rubric the page requested.

**The cheap discriminator is (3), and it needs no new drawings:** re-run the panel with Mark's
rubric stated explicitly — *closer to a correct pelican riding a bicycle; penalise incomplete
frames, broken geometry and floating parts* — and see whether outside raters move off 53%. If they
do, the coin flip was the instruction, not the eye. Separating (1) from (2) still requires the
complexity-matched pool described above.
