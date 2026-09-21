# Result -- measured discordance says A1's corpus is 1.6x short, and the shortfall is authored, not discovered

**2026-09-21. Re-analysis of runs already on disk -- no new GPU time.** Four paired quant
comparisons on the same 16-item `tier_cal` v0 fixture, scored by
`tools/discordance.py` (new). Its sizing table reproduces A1's cell-for-cell except the psi=0.90
column, where the 10-pair floor binds (see below); its Clopper-Pearson intervals were checked
against `scipy.stats.beta` on six cases spanning k=0, 0<k<n and k=n, matching to 1e-6.

**Prior art checked:** `ledger_precheck.py "McNemar discordance rate sample size item count
paired quant comparison" --deep` -> `A1_MEASUREMENT_CORPUS_SPEC.md` (08-20),
`hle-mini/POWER.md` (08-15), `tier4/TIER3_INSTRUMENT_SELECTION.md`.
**What this adds:** A1 computed its sizing table correctly and then entered a **guessed**
discordance rate, saying so in as many words -- *"There is no reason to assume calibration
disagrees at code-generation rates ... We do not know, and the corpus should not pretend to."*
Four paired runs that can supply the number have been sitting in this directory since 09-07.
Nobody had read them as a discordance measurement.

## Sources -- every paired run on this fixture

| pair | separation | packager/box controlled? | raw |
|---|---|---|---|
| L1 AD-IQ2_XS vs L2 AD-IQ3_XXS | 9.21 -> 11.25 GiB | **yes**, one box one binary one packager | `ladder_L{1,2}_rep*.jsonl` |
| L1 AD-IQ2_XS vs L3 AD-IQ3_S | 9.21 -> 12.09 GiB | **yes** | `ladder_L{1,3}_rep*.jsonl` |
| L2 AD-IQ3_XXS vs L3 AD-IQ3_S | 11.25 -> 12.09 GiB | **yes** | `ladder_L{2,3}_rep*.jsonl` |
| Q6_K vs i1-IQ3_M | 21.30 -> ~12.9 GiB | no -- packager differs | `overthink_q6k/armA_rep*`, `overthink/armA_rep*` |

All 16 items x 3 reps, seeds 1001-1003, matched pairwise. **Swift is deliberately excluded**:
quant, packager and tune all move in that pair, so it cannot speak to a quant comparison --
its own receipt says the asymmetry is a property of that pair, not of the training.

## Observed discordance, per arm

Observation level (one pair per item per rep -- what a single-rep campaign would see):

| pair | answerable | unanswerable |
|---|---:|---:|
| L1 v L2 | 16.7 % | 4.2 % |
| L1 v L3 | 16.7 % | **12.5 %** |
| L2 v L3 | 0.0 % | 8.3 % |
| Q6_K v IQ3_M | 4.2 % | **12.5 %** |

**The design-relevant cell is the unanswerable arm at a wide quant gap: 12.5 %**, 95 % CI
[2.7 %, 32.4 %]. Both wide-gap pairs land on it independently, one of them controlled and one
not. The answerable arm's 16.7 % is not a second confirmation -- it is **one broken item**
(`CAL-A6`, which IQ2_XS fails 3/3) counted three times.

**A1 assumed 20 %.** The measurement is **12.5 %**, and lower discordance means *more* items.

## The re-derivation

Holding A1's own psi = 0.70 and swapping in the measured rate, from A1's table:

| discordance | items per arm at psi=0.70 | source of the rate |
|---|---:|---|
| 20 % | 234 -> **A1's working target of 240** | assumed |
| 15 % | 311 | HumanEval+, a different capability |
| **12.5 %** | **374** | **measured here** |

**240 per arm corresponds to psi = 0.745, not to 0.70.** A1's target is not conservative at the
observed rate; it is the number you get by powering for a larger effect than A1 said it wanted
to detect.

**psi is not a quantity to estimate from this pilot.** It is the alternative hypothesis -- the
smallest directional imbalance you want power against. Estimating it from observed flips and
feeding it back into the sizing powers the study for the effect you happened to see. The pilot
supplies the *rate*, which is a nuisance parameter, and nothing else. (For the record the
direction was perfectly consistent within each arm of the controlled ladder, 14/14, and then
**failed to replicate** in Q6_K v IQ3_M, which splits 1/2. Nine discordant observations spread
over four items cannot pin psi tighter than roughly [0.3, 1.0]. Both facts are reported so
neither gets used.)

## Pooling the two arms cancels the effect

A1 says size the arms separately, for a power reason. The data says pooling them is **actively
wrong**. Same pair, `L1` v `L3`, same 48 observations:

| unit of analysis | b | c | psi_hat |
|---|---:|---:|---:|
| answerable only | 0 | 4 | 1.00, every flip toward **higher** bits |
| unanswerable only | 3 | 0 | 1.00, every flip toward **lower** bits |
| **pooled** | **3** | **4** | **0.571 -- indistinguishable from no effect** |

Quantisation moves the two arms in **opposite directions** -- it costs knowledge and buys
abstention, which is exactly what `RESULT_AD_QUANT_LADDER.md` reported as monotone in both
directions at once. A pooled McNemar on this corpus would report a null while both arms were
moving cleanly. This survives whatever psi turns out to be, and it is the one result here that
does not depend on a sizing assumption.

## Cost of the correction: nothing breaks

Using `RESULT_A1_SIZING_MEDIUM.md`'s measured bill (96 tok answerable, 262 unanswerable,
12.15 tok/s end-to-end on `.194` at tensor split, two arms concurrent):

| per arm | tokens | wall clock, two-quant comparison |
|---:|---:|---:|
| 240 (A1) | 85,920 | 1.96 h |
| **374 (measured)** | **133,892** | **3.06 h** |

**1.6x the items costs +1.1 h.** The cost lever was already solved yesterday; the count can
absorb this for free, so there is no budget pressure toward the tidier answer.

## The finding that actually matters: the rate is authored

Across all four pairs, **10 of the 16 items never produced a single discordant observation at
any bitrate**:

```
ever discordant : CAL-A2 CAL-A6 CAL-A7 CAL-U2 CAL-U3 CAL-U6      6/16
inert at every  : CAL-A1 CAL-A3 CAL-A4 CAL-A5 CAL-A8
bitrate           CAL-U1 CAL-U4 CAL-U5 CAL-U7 CAL-U8            10/16
```

Those ten are not weak evidence, they are **zero** evidence, and they stay zero at n=240 or
n=2400. So 12.5 % is not "how often two quants disagree about calibration". It is *how often
they disagree on a corpus written without regard to difficulty*, and 62 % of the authoring
effort bought nothing.

**This makes the discordance rate a design parameter rather than a measurement.** From the same
table:

| if the corpus achieves | items per arm at psi=0.70 | wall clock |
|---|---:|---:|
| 12.5 % (v0 as written) | 374 | 3.06 h |
| 30 % | 156 | 1.28 h |
| 40 % | 117 | 0.96 h |
| 50 % | 94 | 0.77 h |

**Consequence for `RECONCILIATION_BOUNDARY_INSTRUMENT.md`: steps 2 and 3 are one step, and
step 3 comes first.** The rung rebuild was listed as a follow-on to sizing. It *is* the sizing:
graded rungs placed near the act/ask boundary are a mechanism for raising the discordance rate,
and the item count is 47 divided by whatever rate they achieve. A fixture-computed corpus that
puts half its items in the flip zone needs a quarter of the items of one that does not.

## Two smaller corrections

**1. Reps suppress discordance and cost 3x.** Collapsing the three reps by majority vote drops
the measured rate further (Q6_K v IQ3_M unanswerable goes 12.5 % -> 0 %), because majority
voting is designed to discard exactly the near-boundary flipping that McNemar runs on. **A
majority-voted design needs more items at triple the price.** The 374 figure assumes
**one rep per item**. If reps are wanted for a different reason, size on the collapsed rate and
say so.

**2. A1's psi=0.90 column is below POWER.md's own floor, in every cell.** psi=0.90 asks for
9.5 discordant pairs, and `hle-mini/POWER.md` states that below roughly ten the chi2
approximation stops working. `tools/discordance.py` prints the 10-pair floor instead and marks
the cell. Nothing in the campaign plan used that column, so this changes no decision -- it is
flagged so it is not reached for later.

## What this does NOT establish

- **`tier_cal` v0 only.** The argus v2 judgement corpus is a different construction; its
  discordance is unmeasured and must not be assumed to be 12.5 %. The number that transfers is
  the *method*, not the rate.
- **n = 16 items, 3 reps.** The CI on 12.5 % runs to 32.4 %, and the item-level unit is 1 of 8.
  This is a planning estimate from the only data that exists, not a precise rate.
- **Three of the four pairs share a fixture and overlapping items**, so they are not four
  independent replications. The two wide-gap pairs agreeing at 12.5 % is the strongest claim
  available and it rests on partially shared items.
- **Nothing about whether a real effect exists.** This is sizing. Every one of these comparisons
  yielded fewer than 10 discordant pairs and is underpowered by construction -- which is the
  point A1 made and the reason the tool prints that floor on every line.

## Reproduce

```
tools/discordance.py --a ladder_L1_rep*.jsonl --b ladder_L3_rep*.jsonl
tools/discordance.py --size 0.125 0.30 0.40 0.50
```
