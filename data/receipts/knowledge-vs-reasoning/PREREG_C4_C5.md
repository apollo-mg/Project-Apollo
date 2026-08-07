# Pre-registration — C4 (provenance) and C5 (foreign contradiction)

**Logged 2026-08-07, before any C4/C5 inference on either arm.** Probes built and inspected first.

## What is already established

`RESULT_C3_CONTRADICTION.md`: given two competing entries for one question, the pruned arm answers
by **position** (59.1 pp order sensitivity, committed) while the base arm answers by **content**
(6.6 pp).

**Free control, from C2 data already in hand:** this is *not* a general primacy bias. With one
correct entry among three unrelated distractors, the pruned arm scored **100 % / 100 % / 99.1 % /
100 %** across all four positions of the correct entry. Position is irrelevant when nothing
competes. The collapse is specific to **contradiction**.

Two questions follow. Each is one cheap arm.

## C4 — is it fixable?

Same contradiction, each entry tagged with a source. Two deliberately opposed cells:

| cell | layout | asks |
|---|---|---|
| **C4a** | gold **second**, authoritative tag on **gold** | can provenance *beat* position? |
| **C4b** | gold **first**, authoritative tag on the **confabulation** | can provenance *drag it off* the truth? |

Tags: `[Encyclopaedia Britannica, 2026 edition]` vs `[unverified forum post]`.

**C4b is what stops C4a being read as mere tag-following.** A model that blindly follows tags scores
high on C4a *and low on C4b*. Only a model that scores high on both is genuinely using provenance
as evidence rather than as a new positional crutch.

C4a is the direct repair test: in C3, gold-second gave the pruned arm **33.9 %**. Same layout here,
plus a tag.

## C5 — is it about its own prior at all?

Same two-entry contradiction, both orders, but the wrong entry is **another probe's gold from the
same domain** — type-appropriate and plausible (`Ottawa` vs `Avarua`), and *not* this model's own
confabulation.

If the order sensitivity survives, the C3 effect is general contradiction-adjudication failure and
has nothing to do with the model believing its own answer — which would mean my C3 write-up's
framing around "its own confabulation" is incidental and should be corrected.

## Predictions (§8)

| id | prediction | confidence |
|---|---|---|
| **P-C5G** | **GATE** — base order sensitivity on C5 ≤ 20 pp (base stays content-driven on foreign contradictions too) | 0.70 |
| **P-C4a** | pruned C4a ≥ 70 %, i.e. provenance rescues the position failure (C3 baseline: 33.9 %) | 0.55 |
| **P-C4b** | pruned C4b is ≥ 15 pp **below** base C4b — the bad tag drags the pruned arm off truth further | 0.50 |
| **P-C5** | pruned order sensitivity on C5 ≥ 30 pp — the collapse is general, not own-prior | 0.60 |

**P-C5G gates P-C5.** If the base arm also collapses on foreign contradictions, C5 is not the same
instrument as C3 and the arms are not comparable on it.

## Interpretation, fixed before the data

- **C4a high AND C4b high** → provenance is real evidence to this model; label and order your
  chunks and the C3 defect is cheaply mitigated. The optimistic reading survives.
- **C4a high, C4b low** → it swapped one shallow cue (position) for another (tag). Not a fix; it
  would make the model *manipulable* by whoever writes the source labels, which is worse than
  position because it is adversarially controllable.
- **C4a low** → provenance does not reach the decision. The C3 defect is robust and there is no
  cheap prompt-level mitigation.
- **C5 sensitivity high** → general contradiction failure; correct the C3 framing accordingly.
- **C5 sensitivity low** → the effect genuinely involves the model's own prior, and C3's framing
  stands.

## Configuration

Identical to every prior leg: `ikp_run.py` / `ikp_score.py` unmodified, `--no-think`, concurrency 1,
`--max-tokens 64`, temp 0, K=1, `-c 4096 -ngl 99 -sm layer -np 1 --jinja`, `.73` 2×P100 @ 1063 MHz
/ 150 W, G-1a `sigmoid` asserted on both arms. 270 records per arm (C4a 68, C4b 68, C5a 67,
C5b 67). Base runs first (currently resident).

**K=1**, not reproducible on this fleet — existence proof, not rate. At n ≈ 68 per cell, gaps under
~10 pp are not to be read as real.
