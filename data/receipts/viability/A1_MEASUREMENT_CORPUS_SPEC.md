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

## MEASURED 2026-08-21 — the unanswerable arm costs 4-9x its partner

`A5`, computed from the dry-run JSONL (16 items, `Qwen3.8-27B-Q6_K`, effort `xhigh`):

| arm | median chars | mean | max |
|---|---|---|---|
| answerable | 724 | 747 | 933 |
| **unanswerable** | **5,090** | **6,850** | 21,512 |
| unanswerable, non-terminator excluded | 2,877 | 4,755 | 11,414 |

**Ratio: 7.0x median, 4.0x with the non-terminator removed, 9.2x mean.** The spec's guess of
3-6x was low.

At 240 pairs that is **~521k generated tokens ≈ 18.8 h per sweep** on 2× P100 at 7.7 tok/s,
and **~37.6 h for a two-quant comparison** — which is what the corpus exists to do.

Three consequences:

1. **Shrinking the answerable arm saves almost nothing.** It is ~11 % of the cost. The
   "equal power vs control-only" question above was framed as the biggest cost lever; it is
   **not**. The lever is the unanswerable count, and that is the arm carrying the headline, so
   it cannot be cheaply cut. **That open question is settled: size both arms equally.**
2. **A1 does not belong on Pascal.** The 9070 XT runs this model class several times faster
   and `tier_cal` needs no turbo KV — stock f16/q8_0 is verified clean on gfx1201, and the
   codec collapse never touches it. Measure decode there before committing.
3. **Effort is now a cost variable as well as a confound.** Every number above is at `xhigh`,
   which injects *"validate key assumptions"* (`AFM-23`). `medium` injects nothing and may
   generate far less. That makes the effort sweep a prerequisite for sizing, not a follow-up.

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

---

## AMENDMENT 2026-09-07 — the two-arm design has a blind spot; add a third arm

**The two-arm design cannot measure the failure mode that matters most in practice.**

`tier_cal` as specified has an **easy-answerable** arm and an **unanswerable** arm. Measured
2026-09-07 across three effort levels at card sampling (`RESULT_A6_LOW_RUNG.md`), the
answerable arm scored **24/24 at every effort**. A cell that never moves carries no
information: the arm is functioning as a stack-health gate, not as a measurement.

The missing arm is **hard-but-answerable** — questions with a real answer the model may or may
not know. That is the case a user's actual question resembles, and it isolates a distinct
capability:

| arm | the model must judge | our coverage |
|---|---|---|
| easy-answerable | (nothing — it knows) | 24/24, saturated |
| **hard-answerable** | **"do I know this?"** | **ABSENT** |
| unanswerable | "is this question valid?" | measured |

Those last two are different judgements. Our own data shows the effort ladder moves the third
sharply — abstention 13/24 at `xhigh` vs 21/24 at `medium` — while the first is invisible to us.

### Why this amendment exists

Artificial Analysis's AA-Omniscience reports Qwen3.8-27B hallucination as **xhigh 30 %,
low 53 %, medium 67 %** — `xhigh` *best*. Our fixture finds `xhigh` **worst** (confabulation
6/24 vs 3/24). Two checks failed to reconcile them:

- **Split by failure mechanism.** `medium` beats `xhigh` on *both* of our mechanisms
  (fabricated entity 18/18 vs 12/18; false-premise-real-entities 3/6 vs 1/6). Not the cause.
- **NO-STOP scored as "not attempted".** Applying AA's own formula
  (`incorrect / (incorrect + partial + not attempted)`) to our unanswerable arm with the 5/24
  non-terminations counted as abstentions still gives `medium` 12.5 % against `xhigh` 25 %.
  Not the cause either.

The remaining explanation is that **the two instruments measure different capabilities**:
AA-Omniscience is entirely "do I know this?" (every question has an answer, accuracy 16–21 %),
while our unanswerable arm is entirely "is this question valid?". Deliberation plausibly helps
the former and hurts the latter — but our fixture **cannot test that**, because it has no
hard-answerable items.

This is not a claim that AA is wrong. It is a claim that our corpus cannot currently speak to
their axis, and that the disagreement is unresolvable with the instrument as specified.

### Spec change

**Three arms, sized independently.** The hard-answerable arm needs items where the model's
knowledge is genuinely marginal — target ~50 % accuracy at Q6_K/`medium`, since an arm at
100 % or 0 % has no discriminating power (`AFM-15`, and the saturation that killed
`qwen38-lowbit/RESULT_2x2.md`).

Grading needs a third outcome class beyond CORRECT/WRONG: **appropriate abstention on an
answerable item is a distinct outcome from a wrong answer**, and conflating them is what
makes over-abstention invisible. The existing `gate_over_abstention_max` was written for the
easy arm, where it can never fire.

Costing: unmeasured. The A5 ratio (4–9×, and see the units caveat in
`RESULT_A6_EFFORT_NOT_SAMPLING.md` — those figures are characters, not tokens) was measured on
easy-answerable vs unanswerable. A hard-answerable item's cost is between them and has not
been sampled.

**Authoring difficulty is the real cost.** An item at ~50 % model accuracy that is also
verifiable, unambiguous, and not in a training set is much harder to write than either
existing arm — and `A2` (gold verification) applies to every one of them.

---

## DESIGN RULE 2026-09-07 — every item must be satisfiable as RENDERED, not as authored

`AFM-31`: `tier_struct` told the model *"Reply with ONLY a JSON object"* and then appended
*"end your reply with exactly one line: Exact Answer: <your answer>"*. Those cannot both hold.
The defect survived three dry runs because Qwen resolved it silently and passed; it surfaced
only when a model that treats "ONLY" as binding spent 28k characters trying to obey both.

**The rule:** an item is checked against the **rendered** prompt — item text **plus** harness
wrapper **plus** whatever the chat template injects — not against the item text as authored.
`run_tier` honoured `tier.get("prompt")`; `run_struct` did not, and no item-level review could
have caught that because the contradiction did not exist in the fixture file.

### The distinction that keeps this from deleting real findings

| kind | example | verdict |
|---|---|---|
| **Incoherent** — jointly unsatisfiable | "reply with ONLY JSON" + "append a non-JSON line" | **fixture bug**; the model failing is correct |
| **Adversarial** — satisfiable but hostile | `xhigh`'s *"consider plausible alternatives"* on a false-premise item | **the measurement**; do not remove |

The test is **satisfiability, not difficulty**. `RESULT_CLAUSE_DECOMP.md` exists precisely
because the second kind was left in place — it measured *"consider plausible alternatives"*
producing 2/24 NO-STOP against 0/24 for *"validate key assumptions"*.

### Enforcement — structural, not procedural

A rule people must remember failed twice in the same function. Three mechanical checks:

1. **Every tier declares its own `prompt`.** Make it required rather than defaulting to a
   module-level constant. A tier whose items carry full instructions declares `"{q}"`. The
   module default is what silently contradicted the struct items.
2. **Every grader passes it.** `run_struct` did not. When one grader is patched, diff it
   against its siblings — this is the second defect of exactly that shape.
3. **Preflight assertion:** if an item's text contains exclusivity language (`ONLY`,
   `nothing but`, `exactly one`) and the rendered prompt appends any further instruction,
   fail the fixture at load rather than at grading time.

Check 3 is cheap, catches this specific class completely, and needs no semantic reasoning
about the prompt.

**Status:** not implemented. The one-line grader fix lives in `run_fixture_structfix.py` so
historical runs stay reproducible; promoting it is a fixture-version decision.
