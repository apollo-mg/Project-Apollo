# Qwen3.8-27B ranks act-vs-ask on argus in one token (AUROC 0.85-0.92); a 4B NLI judge cannot (0.63). But the request text alone ranks as well, and at the registered rule the judge is no better a gate than the agent

**2026-09-25.** RX 9070 XT. Prereg `PREREG_OPENJEV_JUDGE.md` (commit `34e26e7`, before any forward pass).
- **Data:** `items.jsonl`, 77 argus v5 instruction items (47 act, 30 ask), 40 template clusters.
- **Raw:** `raw/openjev_*.jsonl`, `raw/judge_qwen38-27b-iq3xxs.jsonl`, `raw/logs/`.
- **Scoring:** `analyze.py` produces `RESULT_openjev_judge.json`; `explore_gate.py` produces `EXPLORE_gate.json`
  (exploratory, labelled below).

## The numbers

AUROC of P(ask) against gold ask (0.5 = chance). The 95 % CI is a cluster bootstrap over 40 templates.

| judge | wording | **world** | request only | bal. acc @0.5 (world) | ECE (world) |
|---|---|---:|---:|---:|---:|
| OpenJev 0.8B v5 | W1 rubric | 0.506 [0.33, 0.68] | 0.434 | 0.499 | 0.31 |
| OpenJev 2B v5 | W1 rubric | 0.513 [0.32, 0.70] | 0.422 | 0.521 | 0.18 |
| OpenJev 4B v5 | W1 rubric | **0.628** [0.44, 0.80] | 0.684 | 0.600 | 0.30 |
| OpenJev 4B v5 | W2 yes/no | 0.740 [0.57, 0.88] | 0.775 | 0.642 | 0.18 |
| **Qwen3.8-27B IQ3_XXS** | W1 rubric | **0.848** [0.71, 0.95] | 0.779 | 0.691 | 0.38 |
| **Qwen3.8-27B IQ3_XXS** | W2 yes/no | **0.922** [0.83, 0.98] | 0.921 | **0.806** | 0.17 |
| *the same model as an agent* (`argus-v5` `val_OFF-s1`, thinking on, searching the world itself) | -- | -- | -- | 0.689 | -- |

The agent row is a reference line, not a matched arm. The judge saw the whole world (oracle retrieval); the agent had
to search for it. The agent acted on 46/47 act items and 18/30 ask items.

## Predictions

| # | claim | result | verdict |
|---|---|---|---|
| J1 | OJ-4B W1 world AUROC >= 0.70 | 0.628 | **false** |
| J2 | OJ-4B world beats request-only (CI lower bound > 0) | -0.055 [-0.32, +0.21] | **false** |
| J3 | QJ W1 world AUROC >= 0.80 | 0.848 | **held** |
| J4 | QJ beats OJ-4B (world, W1; CI lower bound > 0) | +0.219 [+0.06, +0.39] | **held** |
| J5 | QJ P(ask) > 0.5 on >= 10 of the 18 ask items the agent over-acted on | 18 / 18 | **held, but uninformative** (below) |
| J6 | OJ size order 0.8B <= 2B <= 4B (descriptive) | 0.506 <= 0.513 <= 0.628 | held |

**Load gates passed on all four arms.**

| gate | 0.8B | 2B | 4B | QJ |
|---|---|---|---|---|
| G1: no load warnings, and the `score` head is byte-equal to the checkpoint tensor | pass | pass | pass | |
| G2: refund demo P(yes) (card 0.07; gate < 0.25) | 0.0054 | 0.0031 | 0.0041 | |
| G3: MNLI-200 accuracy (gate >= 0.75; card 0.896 for 4B) | 0.825 | 0.795 | 0.88 | |
| G4: longest pair (limit 4096) | 1,190 tokens | 1,190 tokens | 1,190 tokens | |
| G5: minimum letter mass | | | | 0.959 |

G1 is as amended by prereg Deviation 1: the matcher was narrowed after it fired on a rope-config notice, and the
score-head equality probe was added, both before any argus item was scored. Every `decide()` result matched the raw triples within 1e-4.

## J5 held for a reason that does not support it

At P(ask) > 0.5, the Qwen judge (W1, world) also stops **29 of the 47 act items**. It says "ask" to nearly
everything, so 18/18 on the over-acted items is its base rate, not insight. **The prediction was mis-specified: it
had no control for how often the judge says ask.** The controlled versions below are exploratory
(`explore_gate.py`):

| QJ | over-acted (18) vs act (47), AUROC | agent-asked (12) vs act, AUROC |
|---|---:|---:|
| W1 world | 0.783 | 0.945 |
| W2 world | 0.889 | 0.972 |

**The "knows but acts anyway" reading does survive the control, weakened.** The judge ranks the items its own
agent over-acted on well above the act items (0.78-0.89). They are harder for it than the items the agent got right
(0.95-0.97), so the agent's failures are not random: it over-acts where the judgement is also less clear-cut.

**As a gate, at the registered rule (W1, world, P(ask) > 0.5):** the judge stops all 30 ask items, including all 18
the agent over-acted on, and it also stops **29 of the 47 act items**. Its balanced accuracy is 0.691, against the
agent's 0.689: no better, with the opposite error. The agent almost never asks when it shouldn't (1/47) and
over-acts on 18/30. The judge never over-acts and asks needlessly on 29/47. Swapping 18 wrong actions for 29
needless questions is not a clear improvement.

**At a fitted threshold (exploratory):** set the threshold where about 9 % of act items are stopped (4/47, the 90th
percentile of act-item P(ask)), fitted on these same items.

| QJ | threshold | ask items stopped | of the agent's 18 over-actions | act items stopped |
|---|---:|---:|---:|---:|
| W1 world | 0.997 | 14 / 30 | 4 | 4 / 47 |
| W2 world | 0.650 | 21 / 30 | 10 | 4 / 47 |
| W1 request only | 0.999 | 8 / 30 | 5 | 4 / 47 |
| **W2 request only** | **0.972** | **22 / 30** | **15** | 4 / 47 |

**At a fitted threshold, the world bought nothing.** Request-only W2 catches more of the over-actions than W2 with
the world (15 vs 10). Its threshold sits at 0.972 on nearly saturated probabilities, so it is fragile: a small shift
in wording or model would move it. Every row here is in-sample and uses oracle retrieval, so these are upper bounds
on what a gate could do, not estimates of what it will do.

**This narrows the J5 reading.** Over-acted vs act ranks at 0.931 from the request alone (W2), above the 0.889 with
the world. So "the 27B has the judgement and the agent throws it away" amounts to something narrower: asked
directly, the 27B sees these requests as under-specified, and the agent acts anyway.

## Most of the ranking is in the request text

The request-only control was meant to catch a judge that reads surface cues. It caught more than that.

- **Qwen:** world minus request-only AUROC is **+0.068 [-0.13, +0.26] (W1)** and **+0.001 [-0.11, +0.12] (W2)**.
  With the plain wording, Qwen ranks ask vs act as well from the request alone (0.921) as with the whole account.
- **OpenJev 4B:** the world is slightly *worse* than no world (J2).

**The world moves calibration, not ranking.** Without it, Qwen says "ask" to everything (mean P(ask) on act items
0.91 for W2 and 0.99 for W1), which is fair, since it cannot verify anything. With it, act items fall to 0.40 (W2):
- balanced accuracy at 0.5 goes from 0.50 to 0.81;
- ECE goes from 0.55 to 0.17.

So the world is what lets the fixed 0.5 rule work, even though the order was already there. With a threshold
fitted per condition it adds nothing (the table above).

**What this says about argus.** Its ask items are lexically marked. The rung ladder moves from "Dave Whitfield's
email about invoice 4471" to "Dave's email" to "Move it to Thursday", so specificity and gold are correlated. That
is partly legitimate (an under-specified request *is* a reason to check), but it is the shallow-cue pass FAILURE_MODES
~L445 warned about, and it means **argus cannot currently tell
a model that reads the world from one that reads the request.** The v5 twins do not help here: they were built to
reach the *same* gold in both worlds (`build_families_v5.py`). The direct test is **flip twins**: the same request
string, act in one world and ask in the other, because the world, not the words, decides it. That is a design note
for argus v6.

## Where each judge fails: calendar arithmetic

Per-class AUROC, W1 world. There are only 3-4 ask and 5-6 act items per class, so this is descriptive.

| class | Qwen | OJ-4B |
|---|---:|---:|
| false-premise | 1.00 | 1.00 |
| scope-before-destructive | 1.00 | 1.00 |
| referent-ambiguity | 1.00 | 0.54 |
| under-determined-recipient | 1.00 | 0.71 |
| unsatisfiable | 1.00 | 0.50 |
| implicit-time-reference | 0.42 | 0.33 |
| mutually-inconsistent | 0.33 | 0.42 |
| conflict-detection | **0.00** | 0.40 |

- **Both judges catch "it doesn't exist":** the Monday standup, "the team", Priya's invoice email.
- **Only Qwen catches "two things match":** the two Daves.
- **Neither can do time arithmetic in a single forward pass:** "after the dentist but before 3pm", or a move that
  lands on another meeting. Qwen's conflict class is fully inverted (0.00): with thinking off it rates the explicit
  moves (0.91-0.99, both act) as riskier than "Do what Dave Okafor asked" (0.86, ask: his Friday morning collides
  with the 1:1).

This matches OpenJev's own card, which scores it weakest on JevBench "temporal_numeric" (0.27) and "ambiguous"
(0.57). A gate built on either judge needs these checks done in code (the scaffold's job in the Minecraft demo),
not by the judge.

## OpenJev specifics

- **Neutral is never used:** the maximum neutral probability over all 616 scored pairs is 2e-5 for 4B and 0.0002 for
  0.8B. In `decide()`'s hypothesis format (`The answer to "..." is ask: ...`) the model is a binary
  contradiction/entailment scorer. "Neutral as abstention" does not exist in this format, which answers the
  prereg's secondary question.
- **Wording matters more than we registered for.** W2 (a plain yes/no, no rubric) beats my W1 rubric for both
  judges:
  - Qwen: W1 - W2 = -0.074 [-0.155, -0.010];
  - OJ-4B: -0.111 [-0.25, +0.02].

  My rubric spelled out the ask conditions. It moved the two judges in opposite directions: Qwen toward ask (mean
  P(ask) on act items 0.64 vs 0.40 under W2) and OpenJev toward act (0.06 vs 0.37). For both, it made the order
  worse. Both wordings were fixed before any run; the registered primary (W1) stays primary.
- **0.8B and 2B are at chance.** Only 4B shows any signal.
- **Contamination:** OpenJev's training mix includes `nvidia/When2Call`, the same call-vs-ask task shape. There
  were no argus or Apollo strings in `code/data_mix.py`.

## Reading, against the prereg's table

- **J1/J2 false:** a 4B NLI classifier cannot carry the act/ask gate here. It reads existence, not ambiguity or
  time, and gets nothing from the world.
- **J3 true; J5 true only after the control, and narrower:** asked directly, the 27B ranks act vs ask well in one
  token, and it ranks the agent's over-actions above the act items. Most of that ranking comes from the request
  wording (0.921 without the world).
- **A self-judge gate is promising, but not shown.** At the registered wording and rule it trades 18 wrong actions
  for 29 needless questions (balanced accuracy 0.691 vs the agent's 0.689). It helps only under the post-hoc
  wording (W2) and a threshold fitted in-sample. A real test needs:
  - a threshold fixed in advance;
  - retrieval by the agent rather than oracle retrieval;
  - flip twins, so the world rather than the wording decides.

  The cost is small: one fixed-choice call with thinking off, under a second (616 calls in 414 s here), and no
  second model.

Two parts should still be code, not the judge: time and conflict checks, and retrieval, since the judge here had
oracle retrieval.

## Not established

- Oracle retrieval. The judge saw the whole 2.8 k-character world, which a real gate would not.
- 77 items in 40 clusters, one quant of the 27B, two wordings, and thinking off.
- The gate operating point is fitted on the same items (exploratory).
- Nothing here measures a gate inside a live agent loop. That is the next test, and it should use flip twins, so
  that the world, not the wording, decides.
