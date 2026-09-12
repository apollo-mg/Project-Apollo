# Result — the thinking cap is a clear win; the injection is unproven, and we found why it could not be tested here

**Run 2026-09-11 22:13–23:23, RX 9070 XT at 330 W.** Pre-registered in
`PREREG_OVERTHINK_INJECTION.md` + Addenda 1–2 (`e507182`, `40329bf`, `ee4e271`, `e50634e`), all
committed before the first generation. Raw: `overthink/`, scoring in `overthink/score_output.txt`.

**Instrument:** `Qwen3.8-27B.i1-IQ3_M` (sha256 `7544860b…0f3cd40`), `run_fixture_structfix.py` —
the baseline's own runner — extended only with `--budget`, `--budget-message`, `--arm`. Card
sampling at `xhigh`, seeds 1001–1003, 16 CAL items × 3 reps × 3 arms = **144 generations, 0 errors**.

## Headline

| arm | ABSTAIN | WRONG | NO-STOP | fail | answerable correct | total thinking |
|---|---|---|---|---|---|---|
| **A** unrestricted | 20 | 3 | **1** | 4/24 | 23/24 | 196,696 chars |
| **B** bare cap | **21** | 3 | **0** | **3/24** | 23/24 | 21,158 |
| **C** injection | 19 | 5 | **0** | 5/24 | 23/24 | 29,240 |

- **The cap works and is free.** NO-STOP goes 1 → 0, and arm C spends **15% of arm A's thinking** on
  the unanswerable arm, with the answerable arm untouched at 23/24 in every arm.
- **The injection did not reduce confabulation.** C is nominally *worst*. Fisher p = 1.00 vs A and
  0.70 vs B — no significance either way.
- **The ADVISOR channel was never used: 0 of 24.** P-O7 and P-O8 are unscoreable.

## Why this design could not test the injection

**The cap fired on only 18 of 24 cells, and the arms diverged on 3.**

Because the server seed makes each request reproducible, arms A/B/C are **the same generation**
until the cap binds. Where thinking stayed under 220 tokens the three arms are byte-identical — and
the scoring confirms it exactly:

| | ABSTAIN | WRONG | NO-STOP |
|---|---|---|---|
| cap did **not** fire (6 cells) — A / B / C | 4 / 4 / 4 | 2 / 2 / 2 | 0 / 0 / 0 |

So the effective sample for the A-vs-B-vs-C contrast is **3 item-reps**, not 24:

| item | rep | A | B | C |
|---|---|---|---|---|
| CAL-U2 | 1 | ABSTAINED | ABSTAINED | ANSWERED-WRONG |
| CAL-U4 | 3 | ANSWERED-WRONG | ABSTAINED | ANSWERED-WRONG |
| CAL-U6 | 2 | NO-STOP | ANSWERED-WRONG | ANSWERED-WRONG |

**No conclusion about the injection's effect is supportable from three cells.** The prereg's power
calculation assumed the Q6_K baseline's 11/24 failure rate; the actual IQ3_M rate is 4/24, so the
headroom the design needed was never there.

## The finding that matters: the detector has a blind spot, and CAL-U3 names it

`NOTE_OVERTHINK_DETECTOR.md` rests on confabulation running **long**. `CAL-U3` — *"In which year did
Mendeleev win the Nobel Prize in Chemistry?"*, which he never did — breaks that premise:

| rep | all three arms | thinking |
|---|---|---|
| 1 | ABSTAINED, `UNKNOWN` | 731 chars |
| 2 | **ANSWERED-WRONG, `1906`** | 651 chars |
| 3 | **ANSWERED-WRONG, `1906`** | 501 chars |

All three arms are identical in all three reps, because **the cap never fires**: 501–731 characters
is well under the 220-token budget. The model does not deliberate its way into `1906` — it answers
quickly and confidently.

**A thinking-length trigger cannot see this failure mode at all.** It is the `medium`/`low` mode from
`RESULT_SEARCH_ASYMMETRY.md` ("answers before deliberating") appearing at `xhigh`, and it is the same
belief the Q6_K model holds on **9/9 runs**. The detector catches runaway search; it is blind to a
confident false belief, which is arguably the more dangerous defect.

## Predictions

| id | prediction | result |
|---|---|---|
| P-O1 | C reduces failures vs A | **FALSIFIED** — 5 vs 4 (p = 1.00) |
| P-O2 | C beats B | **FALSIFIED** — 5 vs 3 (p = 0.70) |
| P-O3 | B increases WRONG vs A | **FALSIFIED** — 3 vs 3, identical |
| P-O4 | C's answerable arm ≥ 22/24 | **CONFIRMED** — 23/24 |
| P-O5 | C does not cannibalise abstention | **FALSIFIED** — C 19 vs B 21 |
| P-O6 | NO-STOP → 0 in B and C | **CONFIRMED** — 0 in both |
| P-O7 / P-O8 | ADVISOR quality and rarity | **UNSCOREABLE** — 0 emitted |
| P-Q1 | IQ3_M arm A fails more than Q6_K's 11/24 | **FALSIFIED** — 4/24, it fails *less* |
| P-Q2 | C reduces failures at IQ3_M | **FALSIFIED** |
| P-Q3 | C's answerable arm ≥ 20/24 | **CONFIRMED** |

**3 confirmed, 6 falsified, 2 unscoreable.** P-O5 falsified without the mechanism predicted: C lost
abstentions to plain confabulation, not to escalation, since ADVISOR was never emitted.

**P-Q1's falsification is the interesting one, and it goes Mark's way.** At matched effort and
sampling, IQ3_M fails **4/24** where Q6_K's baseline fails **11/24** — the low-bit model confabulates
*less*. That is his stated position ("confabulates less and abstains more") and is the premise behind
his counter-prediction **P-Q5**, which remains open until the Q6_K arm runs. The comparison is
cross-node and cross-session, so it is suggestive, not decisive.

## What is shippable from this

**The cap, not the message.** On this corpus a 220-token thinking budget removed the runaway tail
(1 → 0), cut thinking to 15% of unrestricted, and cost nothing on answerable questions (23/24 in
every arm). Arm B — the *bare* cap — was the best arm. That is a smaller claim than the one we set
out to prove, and it is the one the data supports.

## What is not claimed

- **Nothing about the injection's value.** Three divergent cells cannot resolve it. This is a null
  from insufficient headroom, not evidence the idea is wrong.
- Nothing about Q6_K, other models, other efforts, or agentic harnesses.
- Nothing about ADVISOR: never emitted, so its quality is untested.
- **The corpus is now known to be too easy at this bit depth.** A real test needs unanswerable items
  where the baseline actually fails.
