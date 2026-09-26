# Bonsai's thinking loops, read from the logits: `</think>` is never close to sampled mid-trace, the close-or-continue decision is near-deterministic at wrap-up lines, and no logit signal separated loops from long healthy traces

**2026-09-25/26.** Bonsai 2 27B PQ2_0, buun `38ada0e1b` `build_rocm` on the 9070 (validated,
`bonsai-hip/RESULT_BONSAI_HIP_VALIDATION.md`). Prereg `PREREG_LOOP_LOGITS.md` (+ Deviation 1). Prompted by buun's two
points: inspect the logits of a *real* catastrophic loop, because the paper's token list was specific to its own
models; and tell a pathological loop from a legitimately long one before intervening.

- **Replay:** 21 traces from the arm-A (no penalty, `xhigh`) marker-penalty rows:
  - 3 LOOP (capped runaways);
  - 2 LONG-OK (retried past 6,144 tokens but terminated);
  - 16 SHORT.
- **Probe:** every newline boundary plus the end, **1,389 probes**, every one a full prefill (Deviation 1).
- **Raw and scripts:** `raw/full_*.jsonl`, `analyze.py` -> `RESULT_loop_logits.json`; exploratory
  `EXPLORE_wrapup.json`.

## Gates

| gate | result |
|---|---|
| V (incremental vs full prefill, top-20 logprobs within 0.05) | **failed** on tail tokens (max 0.115 at logprob -6 to -16; the true next token is within 0.005 and top-1 agrees 27/27). The registered remedy was applied: **every probe is a full prefill** |
| PC (in terminating traces, P(`</think>`) at the real end is in the top 20 and above the trace's median) | **18/18 pass**. P(`</think>`) at the real end is 0.98-1.00 in every terminating trace |

**Correction to the prereg's table:** it labels LONG-OK CAL-U4 rep 2 "ABSTAINED". That row actually ended
ANSWERED-WRONG ("9013") after 11,294 tokens. It still meets the set's definition ("long but terminated").

## Registered questions

| # | claim | result | verdict |
|---|---|---|---|
| Q1 | each loop has a boundary with P(`</think>`) >= 0.10 before its end | none, in any of the 21 traces | **false** |
| Q2 | loops drift away from stopping (last third < first third) | there is nothing to drift: see below | **false / uninformative** |
| Q3 | < 30 % of the tokens that continue a loop are paper markers | **10.4 %** | **held** |
| Q4 | a length-free signal separates LOOP from LONG-OK early (descriptive) | first-3,000-token top-1 probability: LOOP 0.48 / 0.62 / 0.62, LONG-OK 0.46 / 0.72. Entropy (top-20): LOOP 1.60 / 1.18 / 1.21, LONG-OK 1.68 / 0.83 | **no separation** |

**Why Q1 and Q2 came out this way.** Of 1,368 mid-trace boundaries (all 21 traces), `</think>` appears in the top 20
at only **104**, and its largest value there is **6.6e-5**. At the other 92 % it is outside the top 20, so under
card sampling (`top_k 20`) it **cannot be sampled at all**. At the real end it is 0.98-1.00. Bonsai never "almost
stops" at a paragraph break, in loops or in healthy traces. The registered P(stop) measures a token that is never
in play mid-trace.

## Where the close-or-continue decision is made (exploratory, found after the registered analysis)

Bonsai closes by first writing a wrap-up line. 12 of the 14 terminating traces with at least one boundary open
their final line with **"Need"**. The lines below were selected post hoc: those starting "Need" and mentioning
"final" or "exact answer". They split into two kinds:
- **drafts:** the line contains `Exact Answer: <a value>`;
- **format or decide talk:** "decide final: UNKNOWN or a unit", "maybe output a brief thinking before exact
  answer?".

At the end of either kind, the choice is **almost deterministic**:

| trace, position, line kind | what came next | the model's top choice there |
|---|---|---|
| LONG-OK U4 r2 @11294, draft ("9013") | END | `</think>` 0.999 |
| SHORT U7 r1 @804, draft ("UNKNOWN") | END | `</think>` 0.984 |
| LONG-OK U2 r2 @7957, draft ("UNKNOWN") | re-check | "Double" 0.77 |
| SHORT U5 r1 @1866, draft ("1385") | re-check | "Need" 0.79 |
| **LOOP U5 r2 @5722, draft ("1330")** | re-check (sampled "Let" at 0.06) | **"But" 0.90** |
| LOOP U2 r3 @8049, decide talk | re-check | "But" 0.97 |
| LOOP U2 r3 @9825, format talk | re-check | "Let" 0.996 |

**What the three loops actually did:**

| loop | what happened |
|---|---|
| **U5 r2** | the only one that **drafted an answer and reopened it**. It drafted "1330" at token 5,722; it was still torn between two invented years, 1329 and 1330 |
| **U2 r3** | **circled the decision without drafting**: three decide/format lines, no "Exact Answer: <value>" |
| **U5 r3** | never reached a wrap-up line at all |

**Healthy traces reopen drafted answers too:** LONG-OK U2 r2, SHORT U2 r1, SHORT U5 r1 and SHORT U8 r1 each drafted
an answer, re-checked, and later closed. So "drafted, then reopened" does not separate loops from healthy traces
here.

**The pull-back words are Bonsai's own.** After wrap-up lines, re-checks open with "Double" (as in double-check),
"Let", "Need" and "But". Only "But" and "However" are in the paper's 20. Across all boundaries, the next line starts
with "Let" ("Let's search memory") in **LOOP 23-33 %** of cases vs SHORT 5-15 % and LONG-OK 12-19 %. That is the
only statistic that separated the three loops in-sample, and it was found post hoc.

## What a -4 marker penalty does at these points (computed, approximate)

Applying -4 to the 20 marker ids in the recorded top-20 and renormalizing over those 20 (an approximation: mass
outside the top 20 is ignored):

| point | before | after -4 on markers |
|---|---|---|
| LOOP U2 r3 @8049 | But 0.97, Let 0.02 | **But 0.45, Let 0.41**, Could 0.09 |
| LOOP U5 r2 @5722 | But 0.90, Let 0.06 | **Let 0.51, Double 0.24, But 0.14** |
| LOOP U5 r2 @10703 | Double 0.91 | Double 0.97 |

- **At every reopen point, the re-check still opens.** The penalty changes which word opens it, and `</think>` stays
  outside the top 20, so it cannot close the loop there.
- **So this replay does not explain the marker-penalty run's 3 -> 0 drop in capped runaways.** That drop may come
  from reshaping the re-checks that follow (shorter, different content), or it may be chance: it is 3/48 vs 0/48,
  and it was registered as descriptive for exactly that reason.

## Answering buun's two points

1. **"The tokens were specific to their models":** confirmed. Bonsai's loop vocabulary is enumeration and
   re-verification: bullets "-", "Let", "Maybe", "Could", "Double", "Need". Only 10.4 % of loop continuations are
   paper markers.
2. **"Detect the pathological case before tampering":** no probability-level signal separated loops from
   long-but-healthy traces here.
   - `</think>` gives no gradient.
   - Early entropy and top-1 confidence overlap.
   - Reopening a draft happens in healthy traces too.
   - The only in-sample separator, the "Let" share, is post hoc. It is registered for out-of-sample testing in
     `PREREG_LOOP_DETECTORS.md` before any new traces exist.

**A candidate cause worth testing next.** `xhigh` injects "validate key assumptions" text (INDEX L58,
`qwen38-effort-is-a-prompt-edit`), and "Double"-check is the most common re-check opener. The same items at
`medium`, which injects nothing, would show whether the re-check habit comes from the effort instruction. That
would fit buun's observation that Bonsai needs low or no thinking. On Qwen, `xhigh` was already the NO-STOP
outlier (L58: 0/0/5).

## Correction history

The first version (commit `3b6ec79`) was wrong on four counts, all found in review before anything was quoted:
- its headline, "failure to commit, not to conclude", rested on one of three loops;
- it counted format talk as drafted answers;
- it said "1,494 probes" (the count is 1,389);
- it reported a mid-trace P(`</think>`) of "~1e-7" by averaging the zeros assigned when the token was outside the
  top 20.

## Not established

- 3 loops and 2 long-OK traces, one model, one effort, CAL unanswerable items only.
- A teacher-forced replay of re-tokenized text.
- The wrap-up classification and the "Let" share are post hoc.
- The "legit hard problem" comparison buun describes (a healthy model thinking long on a hard, answerable task)
  is still missing.
