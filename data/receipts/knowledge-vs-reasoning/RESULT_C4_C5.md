# C4/C5 — provenance is not a fix, and the collapse really is about the model's own answer

**Date:** 2026-08-07. Both arms, identical probes, `.73` 2×P100 @ 1063 MHz / 150 W, `tom_default`,
thinking OFF, temp 0, K=1, G-1a `sigmoid` asserted on both. `ikp_run.py` / `ikp_score.py`
unmodified. 270 records per arm, 0 errored, **0/270 truncated on both arms**. Pre-registered in
`PREREG_C4_C5.md`.

## Results

| arm | cell | layout | gold | wrong | refusal | **committed gold** |
|---|---|---|---|---|---|---|
| base | C4a | gold 2nd, AUTH on gold | 58 | 2 | 8 | **96.7 %** |
| base | C4b | gold 1st, AUTH on confab | 26 | 8 | **34** | **76.5 %** |
| base | C5a | foreign wrong, gold 1st | 62 | 0 | 5 | **100.0 %** |
| base | C5b | foreign wrong, gold 2nd | 63 | 0 | 4 | **100.0 %** |
| pruned | C4a | gold 2nd, AUTH on gold | 51 | 7 | 10 | **87.9 %** |
| pruned | C4b | gold 1st, AUTH on confab | 25 | **31** | 12 | **44.6 %** |
| pruned | C5a | foreign wrong, gold 1st | 61 | 1 | 5 | **98.4 %** |
| pruned | C5b | foreign wrong, gold 2nd | 47 | 9 | 11 | **83.9 %** |

| id | prediction | conf | outcome |
|---|---|---|---|
| **P-C5G** | GATE — base C5 order sensitivity ≤ 20 pp | 0.70 | **HELD**, 0.0 pp |
| **P-C4a** | pruned C4a ≥ 70 % | 0.55 | **HELD**, 87.9 % |
| **P-C4b** | pruned C4b ≥ 15 pp below base | 0.50 | **HELD**, +31.8 pp |
| **P-C5** | pruned C5 order sensitivity ≥ 30 pp | 0.60 | **FALSIFIED**, 14.5 pp |

## C4 — provenance looks like a fix and is not one

Adding an authoritative tag to the gold entry lifts the pruned arm from C3's **33.9 %** to
**87.9 %** in the identical layout. Taken alone that reads as a cheap mitigation: label your chunks.

**C4b is why it isn't.** Move the authoritative tag onto the confabulation and the pruned arm falls
to **44.6 %** — below chance — against the base arm's 76.5 %.

```
pruned:  C4a 87.9 %   C4b 44.6 %      <- follows whichever entry is labelled authoritative
base:    C4a 96.7 %   C4b 76.5 %      <- resists the bad label
```

This is the outcome the pre-registration named in advance as *not a fix*: **the model swapped one
shallow cue (position) for another (source tag).** That is worse than the position bias it
replaces, because position is an accident of retrieval order while a source label is
**adversarially controllable** — anything that can write a citation string can steer this model's
answer. A pipeline that "fixes" C3 by adding provenance metadata has built a steering handle.

### The base arm's refusals are the tell

On C4b the base arm **refused 34 of 68** — half the cell — versus the pruned arm's 12. Handed an
authoritative-looking source that contradicts what it knows, the base model declines to answer.
The pruned model commits to the label.

**Detecting the conflict is itself a capability, and pruning cost it.** That is a cleaner statement
of the damage than the accuracy numbers: the pruned model is not merely more often wrong, it is
less able to notice that it is in a situation where it should be uncertain.

## C5 — the falsified prediction confirms C3's framing

I predicted the positional collapse was general contradiction-adjudication failure, with the
"its own confabulation" framing incidental (conf 0.60). **Wrong.**

Identical structure, gold listed second, differing only in what competes with it:

```
competing entry = the model's OWN confabulation   (C3)   ->  33.9 %
competing entry = another probe's gold, same domain (C5) ->  83.9 %
```

**A 50 pp difference from swapping the distractor.** With a foreign wrong answer the pruned arm is
largely fine (14.5 pp order sensitivity, vs 59.1 pp in C3); the base arm is untouched either way
(0.0 pp, 100 % both orders).

So the C3 receipt's framing stands and should not be corrected: **the collapse specifically
involves the model's own damaged prior.** It is not that the pruned model cannot adjudicate
contradictions — it adjudicates foreign ones nearly as well as the base model. It fails when the
competing entry is the thing it would have said itself, which is exactly when retrieval is
correcting it.

That is the worst possible selectivity. Retrieval's whole purpose is to supply what the model has
wrong, and this is the case where the pruned model is least able to accept the correction.

## Combined picture, with the free C2 control

Three conditions now bound the effect, and it is narrow and specific:

| condition | pruned behaviour |
|---|---|
| one correct entry, 3 unrelated distractors (C2) | **100 / 100 / 99.1 / 100 %** across all 4 positions — position irrelevant |
| gold vs a foreign wrong answer (C5) | 98.4 / 83.9 % — mild |
| gold vs **its own confabulation** (C3) | 93.0 / **33.9 %** — collapse |
| gold vs its own confabulation, provenance-tagged (C4) | 87.9 / **44.6 %** — follows the tag instead |

Not a general primacy bias. Not general contradiction failure. **A specific inability to prefer a
retrieved fact over its own damaged prior, which a source label redirects rather than repairs.**

## Limits

- **K=1, temp 0**, not reproducible on this fleet — existence proof, not rate. n ≈ 68 per cell;
  gaps under ~10 pp are not to be read as real. The 50 pp C3-vs-C5 difference and the 31.8 pp C4b
  arm gap are far outside that.
- **C3 vs C5 is a between-set comparison.** C5 dropped one item (67 vs 68) and its distractors are
  drawn from a different distribution than the confabulations. The comparison is like-for-like in
  structure but not item-matched pair-by-pair.
- **Two entries only**; behaviour at realistic k (5–10 chunks) is untested, and primacy effects may
  differ.
- **One tag pair** (`Encyclopaedia Britannica, 2026 edition` / `unverified forum post`). Whether a
  subtler or more plausible provenance signal behaves the same way is unknown, as is whether the
  effect is about authority at all rather than about surface features of the bracketed text.
- Refusal counts are reported raw; the committed-gold metric excludes them by construction, so the
  base arm's 50 % refusal rate on C4b is *not* penalised in its 76.5 %. Both readings are given
  above deliberately.
- One model pair, one prune ratio (25 %), one pruner.
