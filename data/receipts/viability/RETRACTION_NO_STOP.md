# RETRACTION — `NO-STOP` was greedy decoding, not the model

**2026-08-21.** `probe_sampling.py` against `.194` / `Qwen3.8-27B-Q6_K` / `xhigh` /
`n_predict=6144` — **the exact cell where the failure was first observed**. Raw
`probe_sampling.log`.

| condition | chars | finish | answer |
|---|---:|---|---|
| **greedy** — `temperature=0, top_k=1` (every fixture run to date) | **21,512** | `length` | none emitted |
| **card thinking-mode** — `temp=1.0, top_p=0.95, top_k=20` #1 | 7,370 | **`stop`** | **`UNKNOWN`** ✓ |
| **card thinking-mode** #2 | 4,231 | **`stop`** | **`UNKNOWN`** ✓ |

## What is retracted

`RESULT_EFFORT_SWEEP.md` pre-registered the condition for its own retraction:

> *"If recommended sampling removes `NO-STOP`, the only measured difference between effort
> levels here disappears and the finding reduces to a cost result."*

**It removes it.** So:

- **RETRACTED:** *"`xhigh` converts abstentions into non-termination."* All three `xhigh`
  `NO-STOP` items ran greedy. There is no evidence effort causes non-termination under the
  sampling this model is actually tuned for.
- **RETRACTED:** `CAL-U5` and `CAL-U6` as model-level `NO-STOP` findings. Both were greedy.
- **STANDS:** the **cost** result — `xhigh` generated **11.3×** the tokens of `medium` on
  identical items (147,204 vs 13,069 chars). Cost was measured, not inferred from termination.
- **STANDS:** effort changed **nothing** about answering (8/8 everywhere) or confabulation
  (1/8 everywhere, same item every time).
- **STANDS as a harness feature:** the `NO-STOP` verdict class, escalation, and the
  recoverable/lost split are all still the right instrumentation. They correctly detected a
  real failure. The failure was **ours**.

## The actual finding, restated honestly

**Greedy decoding on this reasoning model does not terminate on a false-premise question.**
21,512 characters against 4,231 for the same item at recommended sampling — **5× the tokens to
produce no answer instead of the right one.** That is a harness bug with a model-shaped
signature, which is the most expensive kind, because it presents as a discovery.

## Why it was not caught earlier

`temperature=0` was chosen for determinism and is standard benchmarking practice. The card's
recommendation (`temp=1.0` for thinking mode) was never read until Mark pointed at it. The
choice was never *wrong* as a default — it is wrong **for this model**, and only the model's
own documentation says so.

`AFM-25`: **greedy is not a neutral baseline.** It is a sampling configuration like any other,
and on a reasoning model it has a known failure mode. Read the card's recommended parameters
before running the first arm, not after building a verdict class on the results.

## Cost of the correction

Determinism is what greedy bought, and giving it up is not free:

- `temp=1.0` makes every arm **non-deterministic**, so any rate needs **repeats**, not one pass.
  A1's sizing changes again, upward.
- Existing receipts at `temp=0` are internally consistent and comparable **to each other**, but
  are **not** measurements of the model as intended to be run.

**Open:** does the effort *cost* ratio (11.3×) survive at recommended sampling? Both probe
replicates finished well under the greedy length, which hints the whole `xhigh` cost blow-up may
also be partly greedy. Not measured. **The effort sweep needs re-running at recommended sampling
with repeats before any of it is quoted.**

## A weakness in this probe, recorded

`probe_sampling.py`'s answer extractor is cruder than the fixture's (`split(":", 1)`), and it
labelled the two clean abstentions `ANSWERED` and echoed part of the prompt on the greedy row.
The **verdict here does not depend on it** — `finish_reason` and character counts carry the
result — but the label column in the raw log should not be trusted.
