# B2 resolved: `run_hle_mini.py` is right, `rejudge.py` manufactures answers from truncated drafts

**2026-08-18.** Structural analysis of 57 stored traces across 8 runs. No model calls, no
judge, no GPU. **Aggregate statistics only — no question text, answer text, or per-question
outcomes recorded, per the HLE content-hygiene rule.**

Closes `BACKLOG B2`, which read: *"`run_hle_mini.py` parses `content` only (20 %);
`rejudge.py` parses `content + reasoning` (40-50 %). Two of our own tools disagree on the
same traces. Stricter reading is probably right — truncated reasoning holds drafts, not
conclusions — but 'probably' is not quotable."*

**It is now quotable. The stricter reading is right, and the margin is 7/7.**

## The only difference between the two tools

Both call the **same** `parse_reply` — `rejudge.py:38` imports it from `run_hle_mini`. The
regex is identical. Only the input text differs:

| tool | line | input |
|---|---|---|
| `run_hle_mini.py` | 188 | `parse_reply(text)` where `text = msg["content"]` |
| `rejudge.py` | 77-78 | `parse_reply(content + "\n" + reasoning)` |

## Every disputed parse is a truncated response

The disputed population is the traces where `content+reasoning` finds an answer but
`content` alone does not.

| | count | share |
|---|---:|---|
| traces analysed | 57 | |
| parsed from `content` | 13 | **22.8 %** |
| parsed from `content+reasoning` | 20 | **35.1 %** |
| **disputed (the 7 extra)** | **7** | |
| … with `finish_reason == "length"` | **7** | **100 %** |
| … containing **multiple** `Exact Answer:` strings | 3 | 43 % |

**All seven ran out of tokens mid-reasoning.** Not most — all. And nearly half contain more
than one `Exact Answer:` string inside the chain of thought, i.e. the model wrote several
candidates while working and had not settled on one.

So `rejudge.py`'s extra parses are not recovered answers. They are **drafts scraped out of an
unfinished thought**, and grading them counts a coin-flip as a response.

**This is not a judgment call.** `finish_reason == "length"` means the generation was cut off
— the model *by construction* never emitted a final answer. Any `Exact Answer:` inside that
reasoning is a draft as a matter of definition, not interpretation.

**Fix:** `rejudge.py` must not parse `reasoning` when `finish_reason == "length"`. In this
data that removes the disagreement entirely, because the complementary case — a response that
finished normally, with an empty `content` but an answer in `reasoning` — occurs **zero**
times. If it ever does occur it indicates a chat-template or plumbing fault and should be
fixed there, not papered over by the parser.

## The bigger finding: this was never a parsing problem

Splitting the same 57 traces by whether the model finished:

| | n | content-parsed |
|---|---:|---|
| **truncated** (`finish_reason == "length"`) | **45 (79 %)** | 1 |
| **completed** (`stop`) | 12 (21 %) | **12 / 12 = 100 %** |

**Among responses that actually finish, the content-only parser succeeds every single time.**
The parser has no failure mode in this dataset. The headline "22.8 % parse rate" is almost
entirely the **79 % truncation rate** wearing a parser's clothes.

**Consequence for HLE-mini as a benchmark:** at these budgets it is measuring *"can the model
reach an answer inside the token budget"* far more than *"does the model know the answer."*
Any accuracy number computed over parsed answers is conditioned on a 21 % completion rate,
and the sample that survives is exactly the sample of questions the model found short enough
to finish — a selection effect pointing the same direction as the score.

That reframes the next step: **the budget ladder is the experiment**, not a nuisance
parameter. `results_budget_1024/2048/4096` already exist and each parsed 2/10 from content —
flat across a 4× budget range, which suggests 4096 is still far below what these questions
need, rather than that budget does not matter.

## Method note

Analysis is read-only over the stored traces and reproducible with the snippet in this
directory's history. The trace directories remain gitignored; only counts are recorded here.
