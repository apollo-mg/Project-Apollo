# Result — at Q6_K the cap is a clean win, the injection changed nothing, and we found the structural reason it cannot

**Run 2026-09-12 00:40–02:29 on `.194`** (2× P100, `-sm tensor`, f16 KV, `-c 16384`, Qwen3.8-27B
**Q6_K**). Pre-registered in `PREREG_OVERTHINK_INJECTION.md` + Addenda 1–2, committed before the
first generation. Raw: `overthink_q6k/`. Scored by `tools/score_overthink.py`; output in
`overthink_q6k/score_output_v2.txt`.

**144 generations, 0 errors.** 16 CAL items × 3 reps × 3 arms, card sampling at `xhigh`, seeds
1001–1003, arm order rotated per (rep, item).

> **This receipt corrects the quick score taken at 03:51 on 2026-09-12**
> (`overthink_q6k/score_output.txt`), which concluded *"P-Q5 (Mark) FAVOURED: the injection helps
> more at higher precision."* **That conclusion does not survive the effective-sample check.** The
> A→C improvement it rested on is produced entirely by the thinking cap, which arm B also has.
> Details below; `score_output.txt` is kept as written for the audit trail.

## Headline

| arm | ABSTAIN | WRONG | NO-STOP | fail | median thinking | **model's own** thinking | injected text counted as thinking |
|---|---|---|---|---|---|---|---|
| **A** unrestricted | 19 | 3 | **2** | 5/24 | 2,680 | **181,277** | 0 |
| **B** bare cap | **21** | 3 | **0** | **3/24** | 892 | **20,565** | 828 |
| **C** cap + injection | **21** | 3 | **0** | **3/24** | 892 | **20,565** | 8,910 |

Answerable arm: **24/24 correct in all three arms**, and all three are byte-identical — the cap never
engaged there at all (median 498 chars, well under the 220-token budget).

- **The cap works and is nearly free.** The runaway tail goes 2 → 0 and the model's own deliberation
  on the unanswerable arm falls **88.7%**, from 181,277 chars to 20,565, with no answerable cost.
- **The injection did nothing.** B and C are **identical on every one of the 24 cells** — same
  outcome, and the same own-thinking to the byte.
- **ADVISOR was never emitted: 0 of 144.** P-O7/P-O8 remain unscoreable.

## The arms are one generation, and here is exactly how much of one

A fixed server seed makes A/B/C byte-identical until the cap binds, so the row count is not the
sample size:

| | cells |
|---|---|
| cells per arm | 24 |
| byte-identical across A/B/C (cap never bound) | 6 |
| byte-divergent (cap bound) | 18 |
| **cells where the outcome actually changed** | **2** |

| contrast | cells differing in outcome |
|---|---|
| A vs B | 2 |
| A vs C | 2 |
| **B vs C** — *the injection* | **0** |

The two cells are the whole result:

| item | rep | A | B | C |
|---|---|---|---|---|
| CAL-U2 | 1 | **NO-STOP/REC** | ABSTAINED | ABSTAINED |
| CAL-U4 | 3 | **NO-STOP/REC** | ABSTAINED | ABSTAINED |

Both are runaways that the cap converted into correct abstentions. **Every bit of the 5/24 → 3/24
improvement is the cap.** And all **3 ANSWERED-WRONG cells sit in the byte-identical set** — the same
three generations counted once per arm — so no arm could have affected them. The WRONG column reads
3 / 3 / 3 because it is three generations, not nine.

## Why the injection could not have worked: it arrives after thinking is over

The budget message is delivered **into the reasoning stream, as the last thing in it.** In
`armC_rep1` / `CAL-U5` the reasoning is 1,350 chars, the injected message begins at char 855, and
nothing follows it. The model's deliberation is cut mid-word —

> `…There was "Frisian` → *[injected message]* → end of thinking → `Exact Answer: UNKNOWN`

**This is checked on every cell, not inferred from one.** Of the C rows where the message was
delivered, the message is the final content of the reasoning stream in **18 of 18** here and **20 of
20** in the IQ3_M run — **38 of 38, with zero cells carrying any model text after it.**

So the message's only possible influence is the final answer. It cannot redirect deliberation,
because deliberation is already closed when it arrives. The data confirms this mechanically:
**stripping the injected text, B and C are byte-identical on 46 of 48 cells** (and on the 2 that
differ, the reasoning lengths match exactly and the outcome is the same).

**This is not the experiment we thought we had specified.** The idea was "notice the model is
overthinking and redirect it." What this instrument implements is "hand the model a note at the
instant it is forced to answer." The bare cap already gets that answer right, so there is nothing
left for the note to fix.

**What a real test needs:** the message must arrive while thinking is still open — a mid-stream turn
that re-opens the think block, or a budget that pauses rather than terminates. That is an engine-side
change, not a prompt change, and it is the actual next step for this idea.

## The thinking comparison was inflated, in this receipt and the last one

`len(reasoning)` counts our own injected message as model thinking. Corrected:

| | B | C | C − B |
|---|---|---|---|
| raw `len(reasoning)` | 21,393 | 29,475 | +8,082 |
| injected text | 828 | 8,910 | +8,082 |
| **model's own thinking** | **20,565** | **20,565** | **0** |

The entire apparent difference is the **495**-character message × 18 cells (8,910) less B's
46-character message × 18 cells (828). The same arithmetic applies
to the IQ3_M run (B 20,330, C 20,330). **`RESULT_OVERTHINK_INJECTION_IQ3M.md`'s claim that "arm C
spends 15% of arm A's thinking" is therefore overstated; corrected it is 10.3%**, and C does not
spend more than B. A correction note has been added to that receipt.

## The bet: P-Q4 vs P-Q5 is NOT settled, and last night's score said it was

Mark (P-Q5) predicted the injection helps more at higher precision; Claude (P-Q4) the reverse. The
03:51 score compared arm A to arm C and concluded P-Q5 was favoured:

| | A (control) | C (injection) | A → C |
|---|---|---|---|
| IQ3_M | 4/24 | 5/24 | −1 |
| Q6_K | 5/24 | 3/24 | **+2** |

**That table credits the injection with the cap's work.** Arm B — cap, no message — also scores
3/24 at Q6_K. The correct contrast for the bet is B vs C, and it is empty at Q6_K:

| | B vs C, outcome-differing cells | direction |
|---|---|---|
| IQ3_M | 2 of 24 | both C **worse** |
| Q6_K | **0 of 24** | no effect measurable |

Across both runs the injection changed **2 outcomes in 288 generations**, both for the worse. That
is not evidence for P-Q4 either — two cells cannot support a direction. **Both predictions remain
unresolved, and the proposed `IQ3_M`-under-the-Q6_K-config re-run will not resolve them either,
because the design cannot see the variable.** Fix the mechanism first; the matched re-run is a
question about bit depth, which this instrument does measure, and that is worth running on its own
terms — but it is no longer the thing that settles the bet.

## Predictions

| id | prediction | result |
|---|---|---|
| P-O1 | C reduces failures vs A | **CONFIRMED in direction, misattributed** — 3/24 vs 5/24 (Fisher p = 0.701), but B achieves the same, so the effect is the cap's |
| P-O2 | C beats B | **FALSIFIED** — 3/24 vs 3/24, and 0 of 24 cells differ in outcome |
| P-O6 | NO-STOP → 0 in B and C | **CONFIRMED** — 2 → 0 in both |
| P-O7 / P-O8 | ADVISOR quality and rarity | **UNSCOREABLE** — 0 of 144 emitted |
| P-Q4 / P-Q5 | does the injection help more at low or high precision | **UNRESOLVED** — see above. Previously scored as favouring P-Q5; that scoring is withdrawn |

## An instrument defect worth naming: the ADVISOR false positive

A naive detector (`"ADVISOR" in reasoning + content`) reports **18 emissions** in this run. All 18
are our own injected message echoing back through the reasoning field — the message contains the word
four times. **ADVISOR as an actual answer: 0.** The arms' complete answer vocabularies are:

| arm | distinct answers, unanswerable |
|---|---|
| A | `UNKNOWN`, `1906`, `` (empty, the NO-STOP rows) |
| B | `UNKNOWN`, `1906` |
| C | `UNKNOWN`, `1906` |

`tools/score_overthink.py` now checks the parsed answer field and reports the echo count separately,
so the false positive cannot recur. Had this gone unchecked it would have produced a receipt claiming
a 75% escalation rate for a feature that was never used once.

## Q6_K vs IQ3_M, on what is actually comparable

The two runs differ in node, KV type (f16 vs `q8_0`) and split as well as bit depth, so this is not a
clean bit-depth contrast. Within-run, both agree:

| | IQ3_M (9070) | Q6_K (`.194`) |
|---|---|---|
| A fail | 4/24 | 5/24 |
| B fail | **3/24** | **3/24** |
| C fail | 5/24 | 3/24 |
| A own thinking | 196,696 | 181,277 |
| B / C own thinking | 20,330 / 20,330 | 20,565 / 20,565 |
| B vs C outcome differences | 2 | 0 |
| ADVISOR as answer | 0/144 | 0/144 |

**The bare cap lands on 3/24 at both bit depths.** `CAL-U3` — Mendeleev's Nobel, which he never won —
is answered `1906` at Q6_K exactly as the IQ3_M and historical Q6_K runs answer it. The confident
false belief is unmoved by the cap, by the message, and by bit depth. It remains the failure mode the
detector is blind to, for the reason `RESULT_OVERTHINK_INJECTION_IQ3M.md` gives: it is fast, not slow.

## Instrument hygiene, recorded honestly

- **The per-row config fields are partial.** `effort`, `n_ctx` and `host` were added to the runner
  mid-run and appear on **14 of 144 rows**; `budget_tokens` on 96 (arms B and C only, by design);
  `model` on **0**. All 14 agree: `xhigh`, 16384, `http://10.0.0.194:8095`. The implied `n_ctx`
  recoverable from retry budgets is only a **lower bound** (`>=13312`) because the retry hit the 2×
  ceiling — the recorded field is the authority, and `model` still needs adding to the runner.
- **The Q6_K raw data was untracked in git until this commit.** It was described as "committed and
  safe" in conversation on 2026-09-12; it was on disk and verified, but not in version control.
- **Seeds, item set, sampling and budget are identical across arms**; `sampling` = `card` on all 144
  rows.

## What is shippable

**A 220-token thinking budget, with no message at all.** At Q6_K it removed both runaways, cut the
model's own deliberation by 88.7% on questions with no answer, never engaged on questions that had
one, and cost nothing anywhere (24/24 answerable in every arm). That is the second independent run to
land on arm B as the best arm.

## What is not claimed

- **Nothing about the injection's value.** Zero outcome-differing cells at Q6_K and two at IQ3_M. This
  is a null produced by the *design*, which closes thinking before the message arrives — not evidence
  the idea is wrong.
- **Nothing about ADVISOR.** Never emitted in 288 generations across both runs.
- **Nothing about bit depth** from the Q6_K-vs-IQ3_M table: node, KV type and split all move too.
- **The corpus remains too easy.** Arm A fails 5/24, and 3 of those 5 are one repeated confabulation
  in cells no arm can influence. A harder unanswerable corpus is still the blocking dependency for
  any properly powered version of this experiment.
