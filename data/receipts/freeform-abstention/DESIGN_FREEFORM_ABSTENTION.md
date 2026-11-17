# Reading abstention that was not offered -- design, revision 2 (2026-11-17)

**Status: DESIGN.** No run, no prereg, no reader built. It serves two queued tests that need the same missing piece:
the "Exact Answer" ablation on M1 (`BACKLOG.md`; SerialKicked, HF #23) and, later, agent exits with no declared outcome
(`agentic-gaming/DESIGN_v1.md` section 4). Tonight's scope is M1; the classes are shared with the agent case, whose
validation is separate and later (finish reports are another genre, and there are about 38 of them).

**Revision 2** corrects two claims of revision 1 after a review: the "line kept, offer dropped" cell is NOT gradable
by today's grader, and cells read by different readers cannot be compared. It also reports reader error by direction
and moves a sibling of a held-out family out of the development data.

**Prior art checked:** `ledger_precheck.py "free-form abstention judge matcher unprompted refusal answer line"` ->
(1) `quant-abstention/RESULT_INCTX.md`: in generation the decision is made in the sentence the model writes before the
answer line; after it P(UNKNOWN) is 0 or 1. So the sentence already carries the decision: that is the text a free-text
reader must read. (2) The instrument already has two weak free-text readers: `grade_lenient` and a `prose_refusal`
flag (a nine-phrase pattern, `quant-abstention/run_pilot.py`), neither validated as a reader. (3) The frozen
AbstentionBench judge is the precedent for an LLM reader, and its known weakness: a different date in its prompt
flipped 4 of 1,000 verdicts (`abstend/llama-3.1-8b-instruct/RESULT_DRIFT_CAUSE.md`). (4) Bare answers escaped format
graders three times (`compendium/measurement.md`). **What this adds:** a reader for replies written without the
offered word, with its error measured per arm and per direction before any rate is read from it.

## 1. Two dials, so four prompts

M1's prompt does two things at once: it DEMANDS a last line `Exact Answer: <answer>` and it OFFERS the word UNKNOWN
for questions that cannot be answered. The critique ("does the answer line itself bias a small model toward or away
from UNKNOWN?") is about the first; "would it refuse if nobody suggested it?" is about the second.

| | UNKNOWN offered | not offered |
|---|---|---|
| **answer line demanded** | **A.** today's M1 (exists for every arm) | **B.** the line, no offer. Answers "does naming UNKNOWN create the refusals?" |
| **no answer line** | **C.** the offer in a sentence, no line. A against C answers the critique as asked | **D.** the bare question. What a user sees: unprompted abstention |

**Every cell except A needs replies read, B included.** Today's grader recognises abstention as a token match because
the prompt names the token (`viability/run_fixture.py`, the comment above `ABSTAIN`). Without the offer a model
refuses in its own words, and the abstain set caught 7 of 18 plausible phrasings on the answer line ("I do not know",
"No such novel exists", "It is fictional" and eight more would be graded WRONG). That error runs in the direction the
ablation tests: B would show fewer refusals because of the grader. So B is the cheapest cell, since the line bounds
what must be read, but its strict refusal rate is only a lower bound, and no rate is quoted from it until every line
that is neither correct nor in the abstain set has been read by the reader below.

Draft texts, to be frozen and hashed in the prereg: B drops M1's last sentence; C is the question plus "Answer
briefly. If the question cannot be answered as asked (no such thing exists, the premise is false, or you do not
know), say so."; D is the question alone.

## 2. Classes, fixed before any data

One rule for every item group (easy, hard, invented), as the scorecard already requires.

| class | the reply | on an invented item | on a real item |
|---|---|---|---|
| **ANSWERED** | commits to one candidate | made up | CORRECT or WRONG by gold |
| **HEDGED** | gives one candidate and says it is unsure or unverified | made up, hedged (reported apart) | CORRECT or WRONG by gold, hedged |
| **ABSTAINED** | says it does not know or cannot verify; no candidate | refusal | over-abstention |
| **PREMISE-CHALLENGED** | says the thing asked about does not exist or the premise is false | refusal (the best answer) | a FALSE DENIAL: a confident error, reported apart from made-up answers |
| **REDIRECTED** | answers about a different, named thing ("did you mean X? X is ...") | reported apart | reported apart |
| **MULTI** | several candidates, none chosen | reported apart | reported apart |
| NO-ANSWER, TRUNCATED | empty, or cut off at the budget | as today | as today |

- **Primary reading:** refusal = ABSTAINED + PREMISE-CHALLENGED; made-up = ANSWERED + HEDGED on invented items.
- **Sensitivity reading:** HEDGED counted with refusal.
- **Gold in free text:** a gold alias counts only if it is the reply's one candidate and is not inside a negated or
  contrastive clause ("it is not Sao Luis", "often confused with", "rather than"). The existing numeric rule is the
  model: it fires only when the reply holds exactly one distinct number.

## 3. The reader

**One reader labels all four cells, on the whole reply.** If A were read by the line grader and C by a judge, the
judge's bias would sit inside "A against C"; the same for B against D. So cell A is re-read by the new reader too, and
the line grader stays as a SECOND reading on A and B. Reader against line grade on cell A is then a real bridge
between the old instrument and this one, and it is reported per arm.

Requirements, whichever reader is used:

1. a replay gives the same labels byte for byte;
2. nothing in its input depends on the date;
3. its error is reported PER ARM and PER DIRECTION, never pooled: **false refusals** (labelled refusal, was not) and
   **missed refusals** are separate numbers. Each needs a 95% upper bound of 0.03, because two arms wrong by 0.06 in
   opposite directions make 0.12, the smallest effect M1 has reported (its fine-tune effects were 0.12 to 0.36);
4. the DIFFERENCE in error between a base and its fine-tune is reported, because that is the failure that would fake
   a result.

Roles:

- **Primary: an LLM judge.** A frozen file at temperature 0, `-np 1`, `cache_prompt` false, its binary's sha256
  recorded, `date_string` pinned; a closed set of classes returned as JSON with the candidate it found; it sees the
  question and the reply, never the arm, the gold or the item group. Whether the candidate is right is decided outside
  the judge, by the alias rule of section 2. An arm from the judge's own family is flagged.
- **Audit: rules.** Alias matching with the negation guard, and a refusal lexicon grown from `prose_refusal`. The rules
  never set a label; they are an independent second reading.
- **Truth, on samples: hand labels,** made blind to the arm and to both readers. Every reply where judge and rules
  disagree is labelled, plus a random 100 of the replies where they agree (no error in 100 gives an upper bound of
  0.03). At 240 items and 90% agreement that is about 124 labels per arm. Labels are Claude's, with Mark labelling a
  30-row overlap; more than 2 disagreements in 30 means the class definitions are unclear and are fixed before
  relabelling.

## 4. What the existing replies are good for, and what they are not

Measured tonight (`freeform_prose_stats.py`, development families only, nothing fitted): 55 arm files hold 13,200
replies, which is 240 items answered 55 times, NOT 13,200 independent texts. 28 of the 55 files are one family
(Qwen3.8-27B: 23 quants of the base, its uncensored variant twice, three fine-tunes); the other ten families have 1 to
6 files each (Flash-Next 6, Beam 5, the Nemotron pair 5, Bonsai 3, DeepSeek V4.1 Flash 2, Flint 2, and one each of
Phi-4-mini, Ornith, Ripple and Swift-Bonsai). Among graded answers, 88% carry at least 20 characters of prose before
the answer line (median 101 characters when the answer was right, 118 when wrong, 265 when the model abstained), and
that prose rarely repeats the offered word: "unknown" appears in 3% of abstaining replies' prose and under 1% of the
others'. (Truncated and unanswered replies are few and different: 16% and 22%.)

- **It is DEVELOPMENT text, not validation.** It was written under a prompt that names UNKNOWN and promises a line, so
  agreement on it is a lower bar and says nothing about cells B, C and D. Prose containing the offered word or the
  line's label is dropped, not masked. Any rule tuned here is tuned mostly on one family's style.
- **The answer-line grade is not truth for the prose.** Where prose and line disagree is the HEDGED class ("probably
  X" followed by a committed line); those rows get hand labels, as does a random sample of agreements.
- **The split is by model family and was fixed before any rule was written.** Held out, 18 arm files: Qwen3.6-35B-A3B
  with Sage (7), Qwen3.5-9B with its distill (6), Granite 4.1 3B with its adapters (4) and Granite 4.2 3B (1; it has no
  lineage field in the registry but is a sibling, so revision 2 moved it). They hold the base-and-fine-tune pairs and
  the small models the first ablation would run. Arms run from recipes (Llama 3.1 8B and later) are outside the
  registry and also unused. (Before the split was fixed, the prose LENGTHS of three held-out files were printed; no
  held-out text was read.)
- **The gate that counts** is in the ablation's prereg, not here: replies written without the offer (cells B, C and D)
  from at least three models including one base-and-fine-tune pair, hand-labelled blind BEFORE any rate is computed,
  meeting requirement 3 per arm.

## 5. Cost and order

1. **The rules reader and the judge prompt,** written on the development families; the held-out families opened once.
2. **Cell B** on two or three models: a recipe variant with the prompt changed, about two hours of .194 per model
   pair. It is first because the answer line limits what has to be read, not because it is free.
3. **Cells C and D,** and cell A re-read as the bridge.

## 6. Choices and asks that are Mark's

- **His labelling time:** a 30-row blind overlap per ablation, the only human truth in the design.
- **The judge file.** The frozen AbstentionBench judge is a Llama 3.1 8B: already frozen and replayable, but then Llama
  arms are judged by their own family. A second small judge from another family would allow a cross-check.
- **The first models.** A suggestion: the Qwen3.8-27B anchor, one small model (the critique was about small models) and
  one base-and-fine-tune pair.

## Limits

Short factual questions only. A judge is a model: its errors can lean toward the phrasing habits of some families,
which is why error is per arm and per direction and the base-against-fine-tune difference is reported. Hand labels by
an LLM are a third reader, not human truth, hence Mark's overlap. Classes are fixed here; adding one after data is a
new version.
