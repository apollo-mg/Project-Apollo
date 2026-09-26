# Pre-registration -- what does a Bonsai thinking loop look like in the logits, and can it be told apart from legitimately long thinking?

**2026-09-25 ~21:50, before any trace is replayed.** Exploratory mechanism work. It was prompted by buun (Discord,
21:31-21:41):
- *"replicate a real catastrophic case and then have Claude inspect the logits, because the tokens they suggested
  were specific to like their own models"*;
- *"it should probably detect a pathological case before it starts tampering with things -- there can be a
  legitimately hard problem that e.g. Q8 takes its time thinking about, that should be differentiated somehow from
  the pathological case in Q1"*.

**Prior art checked:** `ledger_precheck.py "thinking loop stop probability end of think logits runaway"` -> receipts
found:
- L46: a bare thinking cap removes the runaway tail;
- L47: thinking *length* as a confabulation detector (82 % of failures at >= 1,000 chars, 0 % of correct answers, on
  CAL);
- `RESULT_MARKER_PENALTY_BONSAI.md`: the 20 paper markers are **not** denser inside Bonsai's capped loops (2.3-2.5
  per 1k chars) than in its normal thinking (2.6). The loops are search spirals on questions with no answer, not
  repetition.

**What this adds:** the first per-position logit view of those loops. It is length-free, so it could matter where
long thinking is legitimate (which L47's length rule cannot handle).

## Instrument

- **Model:** Bonsai 2 27B PQ2_0 (sha256 `3907dc16...`), buun `38ada0e1b` `build_rocm` on the 9070. This path was
  validated today (`bonsai-hip/RESULT_BONSAI_HIP_VALIDATION.md`). Settings: `-c 16384 -np 1`, f16 KV, static.
- **Traces:** the stored `reasoning` of rows in `marker-penalty/raw/out_bonsai{1,2}` (arm A, no penalty, `xhigh`,
  card sampling). They are re-rendered through `/apply-template` with the runner's exact single user message
  (`tier_cal.prompt`) and `reasoning_effort: xhigh`, then re-tokenized. The prompt ends `<think>\n`.
  Re-tokenization of generated text can differ from the sampled token sequence; the count of mismatching positions
  is not observable, so this is a teacher-forced replay of the *text*.
- **Probe:** at each boundary (the position right after a token containing a newline, at least 2 tokens after the
  previous probe), plus the end of the trace, `/completion` is called with:
  - the prefix, `n_predict 1`, `n_probs 20`;
  - the true next token forced by `logit_bias +100`, so the cache only ever extends (no recurrent rollback).

  The server reports the **raw** distribution: checked with a forced token at logprob -20.1 while the model's own
  top choice was 0.978.
  - **Recorded:** top-20 logprobs and the true next token's logprob.
  - **P(stop)** = P(`</think>`, id 248069) when it is in the top 20, else 0. Under card sampling (`top_k 20`) a
    token outside the top 20 cannot be sampled, so this is exactly the per-boundary chance of ending the thinking
    block.

**Replay validity gate (V):** every 25th probe is re-sent with `cache_prompt: false` (a full prefill through the
validated `-b` path). The max |delta logprob| over the shared top-20 must be <= 0.05. If it fails, the incremental
path is not trusted and every probe is re-run as a full prefill.

**Positive control (PC):** in each *terminating* trace, P(`</think>`) at the final position (the text actually ended
there) must be in the top 20, and it must exceed that trace's median boundary P(stop). If this fails, the probe
does not measure stopping.

## Traces

| set | what | rows |
|---|---|---|
| **LOOP** | capped runaways, arm A | CAL-U2 rep 3, CAL-U5 reps 2 and 3 |
| **LONG-OK** | the same model, long (retried past 6,144 tokens) but terminated | arm A CAL-U2 rep 2 (ABSTAINED), CAL-U4 rep 2 (ABSTAINED) |
| **SHORT** | ordinary terminating traces, for scale | arm A, one rep of every other item (reps chosen as rep 1) |

Qwen IQ3_XXS's own long traces (buun's "Q8 takes its time" case) are **not** in this pass: that needs a second model
on the card. It is the follow-up, alongside SWE-bench problem statements, which give legitimately hard problems.

## Questions and predictions

| # | claim | test | conf |
|---|---|---|---:|
| Q1 | Loops nearly stop and get pulled back | each LOOP trace has >= 1 boundary with P(stop) >= 0.10 before its end | 0.50 |
| Q2 | Loops drift away from stopping | in each LOOP trace, mean boundary P(stop) over the last third < over the first third | 0.50 |
| Q3 | Bonsai's own loop lexicon is not the paper's | at LOOP boundaries, fewer than 30 % of the true next tokens are among the 20 paper markers | 0.70 |
| Q4 | A length-free signal separates LOOP from LONG-OK early | descriptive: over the first 3,000 trace tokens, compare max P(stop), mean top-1 prob and the fraction of boundaries whose top-1 is a "continue-searching" token between the two sets. With 3 vs 2 traces, **no test is possible**; this is a pointer for the SWE-bench follow-up | -- |

**Descriptive outputs:**
- the per-trace P(stop) trajectory;
- the top 20 true next tokens at LOOP boundaries vs at LONG-OK boundaries;
- the tokens that win at the highest-P(stop) boundaries of each loop (what pulls it back).

## Not established by design

- n = 3 loops and 2 long-OK traces from one model at one effort.
- A teacher-forced replay of re-tokenized text.
- CAL unanswerable items only, not real hard problems. The "legit hard problem" comparison buun describes needs
  SWE-bench-style prompts and a healthy model; this pass only prepares that.
