# Bonsai's thinking loops, read from the logits: `</think>` is never a mid-trace decision, and the loop is a failure to *commit*, not a failure to conclude

**2026-09-25/26.** Bonsai 2 27B PQ2_0, buun `38ada0e1b` `build_rocm` on the 9070 (validated,
`bonsai-hip/RESULT_BONSAI_HIP_VALIDATION.md`). Prereg `PREREG_LOOP_LOGITS.md` (+ Deviation 1). Prompted by buun's two
points: inspect the logits of a *real* catastrophic loop, because the paper's token list was specific to its own
models; and tell a pathological loop from a legitimately long one before intervening.

- **Replay:** 21 traces from the arm-A (no penalty, `xhigh`) marker-penalty rows:
  - 3 LOOP (capped runaways);
  - 2 LONG-OK (retried past 6,144 tokens but terminated);
  - 16 SHORT.
- **Probe:** at every newline boundary, with every probe a full prefill (Deviation 1), 1,494 probes in total.
- **Raw and scripts:** `raw/full_*.jsonl`, `analyze.py` -> `RESULT_loop_logits.json`; exploratory
  `EXPLORE_wrapup.json`.

## Gates

| gate | result |
|---|---|
| V (incremental vs full prefill, top-20 logprobs within 0.05) | **failed** on tail tokens (max 0.115 at logprob -6 to -16; the true next token is within 0.005 and top-1 agrees 27/27). The registered remedy was applied: **every probe is a full prefill** |
| PC (in terminating traces, P(`</think>`) at the real end is in the top 20 and above the trace's median) | **18/18 pass**. P(`</think>`) at the real end is 0.98-1.00 in every terminating trace |

**Correction to the prereg's table:** it labels LONG-OK CAL-U4 rep 2 "ABSTAINED". That row actually ended
ANSWERED-WRONG ("9013") after 11,294 tokens. It still meets the set's definition ("long but terminated"), so the
comparison stands.

## Registered questions

| # | claim | result | verdict |
|---|---|---|---|
| Q1 | each loop has a boundary with P(`</think>`) >= 0.10 before its end | **0 such boundaries in all 21 traces** | **false** |
| Q2 | loops drift away from stopping (last third < first third) | the per-third means are all ~1e-7; 2 of 3 fall, 1 rises | **false / uninformative**: there is no signal to drift |
| Q3 | < 30 % of the tokens that continue a loop are paper markers | **10.4 %** | **held** |
| Q4 | a length-free signal separates LOOP from LONG-OK early (descriptive) | first-3,000-token top-1 probability: LOOP 0.48 / 0.62 / 0.62, LONG-OK 0.46 / 0.72. Entropy (top-20): LOOP 1.60 / 1.18 / 1.21, LONG-OK 1.68 / 0.83 | **no separation** in these statistics |

**Why Q1 and Q2 came out this way.** `</think>` sits at about **1e-7** at every mid-trace newline boundary, in loops
and in healthy traces alike, and at about **1.0** at the real end. Bonsai never "almost stops" at a paragraph break.
The registered P(stop) measures the wrong token for a mid-trace decision. The next section finds where the
decision actually lives.

## Where the stop decision actually lives (exploratory, found after the registered analysis)

Bonsai closes by first writing a wrap-up line. 12 of the 14 terminating traces with at least one boundary open
their final line with **"Need"** ("Need final exactly: Exact Answer: 9013"). The decision to close or continue is
made **at the end of each wrap-up line, and it is almost deterministic either way**:

| after a "Need ... final / Exact Answer" line | what came next | P(`</think>`) | model's top choice |
|---|---|---:|---|
| LONG-OK U4 r2 @11294 "Need final exactly: Exact Answer: 9013" | END | 0.9995 | `</think>` 0.999 |
| SHORT U7 r1 @804 "Need final: Exact Answer: UNKNOWN" | END | 0.984 | `</think>` 0.984 |
| SHORT U2 r1 @3982 "Need final with exactly one line: "Exact Answer: UNKNOWN"..." | re-check | 0 | "Double" 0.55 |
| **LOOP U5 r2 @5722 "Need final: Exact Answer: 1330."** | re-check | **0** | **"But" 0.90** |
| LOOP U2 r3 @8049 "Need decide final: UNKNOWN or a unit..." | re-check | 0 | "But" 0.97 |
| LOOP U2 r3 @9825 "Need maybe output a brief thinking before exact answer?..." | re-check | 0 | "Let" 0.996 |

- **Re-checking after drafting an answer is normal.** Healthy traces also reopen a drafted answer one or two times
  before closing: SHORT U2, U5, U7 and U8, and both LONG-OK traces. **The loops are traces whose re-check never
  lands.**
  - LOOP U5 r2 drafted "Exact Answer: 1330." at token 5,722, reopened (it was torn between two invented years, 1329
    and 1330), drafted again at 10,703, reopened again, and hit the cap.
  - LOOP U2 r3 drafted three times.
  - LOOP U5 r3 never drafted at all.
- **The pull-back words are Bonsai's own:** after wrap-up lines, the re-check opens with "Double" (0.5-0.9), "But",
  "Let" and "Need". Only "But" and "However" are in the paper's 20.
- **"Let" rises with loopiness** (the share of boundaries whose next line starts "Let", as in "Let's search memory"):
  SHORT 5-15 %, LONG-OK 12-19 %, **LOOP 23-33 %**. Descriptive, 3 loops.

**What this means for a logit penalty.** At the point where a loop reopens, P(`</think>`) is effectively 0 and the
re-check opener has 0.9+. Penalizing "But" there does not make the model stop; the mass moves to "Let" or "Double",
which are unpenalized, and it re-checks anyway. That fits the marker-penalty result: fewer capped runaways, answers
unchanged. The penalty can shorten or reshape re-checks, but it cannot supply the missing commitment.

## Answering buun's two points

1. **"The tokens were specific to their models":** confirmed. Bonsai's loop vocabulary is enumeration and
   re-verification: bullets "-", "Let", "Maybe", "Could", "Double", "Need". Only 10.4 % of loop continuations are
   paper markers.
2. **"Detect the pathological case before tampering":** no probability-level signal separated loops from
   long-but-healthy traces here.
   - `</think>` gives no gradient to watch.
   - Early entropy and top-1 confidence overlap.
   - The difference is in the **content**: a loop drafts the answer and reopens it because it is still choosing
     between candidates, often invented ones on these unanswerable items.

   So a detector probably has to read what is being re-checked, for example "the same final-answer line drafted and
   reopened N times", or "alternating between the same two candidates". That is a job for code or a cheap judge
   reading the thinking stream, not a logit threshold.

**A candidate cause worth testing next.** `xhigh` injects "validate key assumptions" text into the prompt (INDEX
L58, `qwen38-effort-is-a-prompt-edit`), and "Double"-check is the most common re-check opener. The same items at
`medium`, which injects nothing, would show whether the re-check habit comes from the effort instruction. That
would fit buun's observation that Bonsai needs low or no thinking. On Qwen, `xhigh` was already the NO-STOP outlier
(L58: 0/0/5).

## Not established

- 3 loops and 2 long-OK traces, one model, one effort, CAL unanswerable items only.
- A teacher-forced replay of re-tokenized text.
- The wrap-up analysis is post hoc: its line classification ("Need" + final / exact answer) was chosen after seeing
  the data.
- The "legit hard problem" comparison buun describes (a healthy model thinking long on a hard, answerable task)
  is still missing. It needs SWE-bench-style prompts on Qwen3.8; that is the follow-up.
