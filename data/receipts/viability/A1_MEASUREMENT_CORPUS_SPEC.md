# A1 — spec for the calibration MEASUREMENT corpus

**2026-08-20.** Design for the corpus that `tier_cal` deliberately is not.
`CALIBRATION_TIER_DESIGN.md` registers the 16-item gate; this specifies the instrument that
can carry a *comparison*. **Not built. This is the spec, and the construction is the part
worth arguing about before anyone authors items.**

## Why the gate cannot be promoted

At n=8 per arm, the Wilson 95 % interval on a confabulation rate of **2/8 is [7 %, 59 %]** —
a threefold range. On 4/8 it is [22 %, 78 %]. One item moves the rate 12.5 points. The gate
answers *"did confabulation blow up"*; it cannot answer *"is IQ2 worse than Q6 here"*, and
no amount of careful reading of a gate result changes that.

## Sizing — the requirement is on discordant pairs, not items

McNemar power comes only from pairs where the two conditions **disagree**. Items both quants
get right, or both get wrong, contribute nothing. Normal approximation, 80 % power, α = 0.05:

| disagreement | ψ=0.60 | ψ=0.65 | ψ=0.70 | ψ=0.75 | ψ=0.80 | ψ=0.90 |
|---|---|---|---|---|---|---|
| 5 % | 3877 | 1697 | 933 | 579 | 386 | 190 |
| 10 % | 1939 | 849 | 467 | 290 | 193 | 95 |
| **15 %** | 1293 | 566 | **311** | 193 | 129 | 64 |
| 20 % | 970 | 425 | 234 | 145 | 97 | 48 |
| 30 % | 647 | 283 | 156 | 97 | 65 | 32 |
| 40 % | 485 | 213 | 117 | 73 | 49 | 24 |

*(ψ = the share of discordant pairs falling one way; 0.5 is no effect.)*

The 311 figure carried over from `../tier4/TIER3_INSTRUMENT_SELECTION.md` is the **15 %/0.70
cell**, and 15 % was HumanEval+'s disagreement rate. **There is no reason to assume calibration
disagrees at code-generation rates.** Calibration is the fragile capability — that is the whole
premise of the tier — so disagreement between a Q6 and an IQ2 may well be 30–40 %, which puts
the requirement nearer 120–160. It could also be lower. **We do not know, and the corpus should
not pretend to.**

**Consequence for the design:** size for the pessimistic end, and make the analysis **report the
achieved discordant count** rather than assume power. A run that yields 12 discordant pairs is
underpowered no matter how many items it contained — that is precisely how HumanEval+ died, and
a corpus that reports only a rate would hide it a second time.

**Working target: 240 unanswerable + 240 answerable = 480 items.** The coverage is **per arm**,
not from the total: 240 items is the 20 %/ψ=0.70 cell (234), so each arm independently reaches
that point. It does **not** mean 480 buys 480 items' worth of power on one question — the two
arms answer different questions and are sized separately. Equal sizing gives the answerable arm
the same power so
"over-abstention did not change" is a claim rather than an assumption. The answerable arm is
not decoration: without power there, a rise in confabulation cannot be distinguished from the
model simply answering more of everything.

## Construction — make unanswerability DECIDABLE, not asserted

The v0 gate's largest liability is `A2`: sixteen items whose golds and whose *unanswerability*
are both asserted from memory. That does not scale to 480, and hand-verification of 480 invented
entities is not a real plan.

**The fix is to generate both arms from closed sets.** Pick a category whose membership is
finite, enumerable and authoritative. Then:

- **answerable item** = a question about a **member**, gold from the same source
- **unanswerable item** = the identical question template about a **non-member**

Unanswerability stops being a claim and becomes a **set-membership decision**. The two arms are
matched on template, domain and phrasing by construction — the obscurity matching that
`AFM-22` demands stops depending on the author's judgement.

Candidate sets (each fully enumerable and stable): chemical elements; SI base and named derived
units; Canadian provinces and territories; US states; Shakespeare's plays; the standard amino
acids; IANA well-known ports; Nobel laureates by year and category; Olympic host cities; ISO
3166 country codes; the Great Lakes; a named author's published bibliography; Apollo mission
numbers; planets and their moons above a stated size.

## Plausible surface — the second half, and the harder one

Closed-set membership gives decidable falsity. It does **not** give plausible surface, and
`AFM-22`'s second layer is that a fake with an orthographic tell measures pattern-matching
rather than calibration.

**Draw non-members from real names in an adjacent category.** A Canadian *town* named as a
province. A real country that no element is named after, in a set where elements *are* named
after countries. A real Shakespeare *character* named as a play. A real author's real
contemporary's title attributed to them. Every surface is a genuine name; only the
*relationship* is false. Nothing in the string tells the model anything.

That combination — **plausible surface from real adjacent entities, decidable falsity from
closed-set membership** — is the whole design. Each half fixes what the other cannot.

### The alias trap

The one way closed-set membership silently fails: a non-member that is a member **under another
name**. `cassiopeium` is lutetium. `Ceylon` is Sri Lanka. `Peking` is Beijing. Columbium is
niobium. An item built on any of those inverts — it punishes a model for being right, and it
does so invisibly because the generator "verified" membership against a list that did not
contain the alias.

**Every closed set needs a curated alias list, and the alias list is manual.** Treat it as the
irreducible hand-work: it is far smaller than 480 items and it is the only place the
construction can quietly betray us.

## What stays manual

1. Choosing the sets and writing one template per set.
2. The alias list per set.
3. A plausibility read of the generated non-members — a template can still produce something
   absurd, and one absurd item is a tell.
4. Deciding whether a template's question is *genuinely* answerable for every member. "Which
   year did X win the Nobel?" is fine; "what is X famous for?" is not gradeable.

## Repetition is a tell too

15 items from one template is a pattern a model can latch onto within a run, and a 480-item
corpus built from 16 templates would be 30 repeats each. **Cap items per template** (~8) and
carry more templates (~60), or vary the phrasing per item from a small set of surface forms.
Untested, and worth an explicit check: if per-template outcomes are near-identical, the corpus
is measuring templates, not knowledge.

## Open, and genuinely undecided

- **Does the answerable arm need equal power, or is it a control?** Equal power doubles the
  corpus. The argument for it is above; the argument against is that a control only needs to
  rule out a *large* timidity shift, which needs far fewer items. **This is the single biggest
  cost lever in the spec.**
- **Effort interaction.** More reasoning gives a model more chance to notice a false premise.
  `reasoning_effort` may move calibration more than quantisation does — in which case it is a
  confound that must be pinned, and possibly an axis worth measuring in its own right. Nothing
  here has tested it.
- **Is the offered hatch the right channel at this size?** It matches AA and it grades cleanly,
  but it measures compliance with an instruction as much as calibration. A volunteered-uncertainty
  variant on a subset would show how much of the score is the hatch.
