# The ledger reported `ok` for 8 unusable entries out of 18

**2026-08-30.** Triggered by a question about how the `.73` on-demand fallback performed
overnight. The fallback performed fine. The audit it prompted did not.

## What the heartbeat said, and what was on disk

Every section since launch, classified:

| day | sections | verdict |
|---|---|---|
| 2026-08-27 | 5 | 4 ok, **1 degenerate `////`** |
| 2026-08-28 | 7 | 1 honest skeleton, **5 degenerate `////`**, **1 raw reasoning** |
| 2026-08-29 | 4 | 1 honest skeleton, 3 ok |
| 2026-08-30 | 2 | 1 ok, **1 raw reasoning** (before repair) |

**8 of 18 sections unusable — 44%.** Six are 100 % `/` characters. Two are the model's
chain-of-thought instead of an entry. **Every one of those runs wrote `status":"ok"`**, and the
hourly human observer reported `ok` alongside them.

Both observers checked whether the process *ran*. Neither checked whether it *produced anything*.
The heartbeat is not the product.

## Two distinct defects, one of them much older than it looked

**1. Reasoning leakage.** `ledger_build.py` had no chain-of-thought stripping at all — zero
occurrences of the string `think` in the file.

The first fix was wrong in an instructive way. A `<think>.*?</think>` regex matches nothing here:
Qwen-family templates pre-fill the *opening* tag inside the prompt, so the completion carries only
a closing tag. The second attempt — cut through the **last** `</think>` — destroyed 1.3 KB of a
finished entry, because that entry contained a second, unpaired closing tag in the middle of the
prose. Correct rule, now implemented: drop paired spans, treat the **first** unpaired closing tag
as the end of the pre-filled block, and delete any later tag as a stray marker while keeping the
text around it.

**2. Truncation, which stripping cannot fix.** `max_tokens` was 2048. A reasoning model spends
that budget thinking before it writes anything, so the response ends mid-thought with no closing
tag — nothing to strip, and no heuristic can tell a cut-off entry from a terse one. Raised to
6144 and, more importantly, `finish_reason == "length"` with no closing tag is now a hard failure
that falls back to the mechanical skeleton. The `////` runs are the same family: degenerate
generation that the pipeline accepted as prose.

## Correction to my own first reading

I initially told Mark the `.73` fallback had *introduced* this. That was wrong. `.73` introduced
only the visible symptom — literal `</think>` tags, which no prior day had. The underlying
failure (unusable entries accepted as `ok`) dates to 2026-08-27, the day after launch, and the
worst day by far is 2026-08-28, served entirely by the `.194` endpoints.

The fallback did not break the ledger. It made a two-day-old silent failure legible.

## Fixes

| file | change |
|---|---|
| `tools/ledger_build.py` | `strip_reasoning()`; `max_tokens` 2048 -> 6144; `finish_reason == length` raises |
| `tools/ledger_validate.py` | new — rejects think tags, degenerate repetition (>40 % one non-alnum char), planning language, mid-sentence starts |
| `tools/ledger_validate.sh` | wrapper so both observers share one check |
| `tools/ledger_notify.sh` | human path alerts on a bad entry, not just a bad heartbeat |
| `tools/ledger_health.sh` | agent path escalates the same into `DRIFT_WARNING.md` |
| `tools/ledger_run.sh` | every beat appends to `.ledger_beats.jsonl` (append-only history) |

## Verification

- Validator re-run over all 18 historical sections: catches all 8 bad ones, passes all 10 good
  ones. No false positives on the known-good days.
- Three consecutive real model calls through `.73` on the fixed path: 3/3 clean, 1797–2132 bytes.
- Full `ledger_run.sh`: `rc=0`, beat appended, both observers green.
- Today's polluted entry repaired from backup with the corrected rule (2134 bytes recovered vs
  1138 under the wrong one).

## Why unit tests did not catch this

The `strip_reasoning` unit tests passed on the first, wrong implementation, and passed again on
the second, wrong one. Both times the defect surfaced only from running the real pipeline against
the real model and **reading the output**. The truncation case in particular is invisible to any
test that feeds it well-formed input, because the failure is that the input is not well-formed.

## Endpoint order inverted, and the loop now falls through

Mark's read of the `////` cluster: *"we were probably troubleshooting and had bad endpoints
available at a higher priority to the ledger than a working endpoint."* That fits the record —
2026-08-28 is the day `.194` was serving DS4 and Flash-Next under tensor-split configs, and
`////` is the exact signature of the `head_count_kv` bug characterised on 2026-08-30.

It also exposes a second flaw independent of ordering: the host loop committed to the **first
endpoint returning 200** and never reconsidered. A broken model passes `/health` identically to a
good one, so a 200 was never evidence about output.

Two changes:

1. **Order inverted.** `HOSTS` now leads with the `.73` wake proxy, with the `.194` endpoints as
   fallback. `.194` is the experiment box and whatever is loaded there is often something we are
   actively breaking; `.73` runs a known-good pinned model. Correctness now outranks the cost of
   waking a sleeping node. That cost stays bounded by the existing idle gate — a cycle with <25
   new events exits before touching any host, which is why `.73` slept 17h26m straight overnight
   even with the fallback already wired in.

2. **`ledger_build.py` exits 2 on a malformed entry**, before appending, so `ledger_run.sh`
   falls through to the next endpoint instead of writing garbage. Endpoint choice and output
   validity are separate defences on purpose.

### Verified against a deliberately broken endpoint

A stub server that answers `/health` with 200 and generates 1800 `/` characters, placed **first**
in `LEDGER_HOSTS` ahead of the `.73` proxy — i.e. a reconstruction of 2026-08-28:

```
build failed/rejected against http://127.0.0.1:8091:
  REJECTED entry from http://127.0.0.1:8091: degenerate output — 100% of the entry is '/'
{"ts":...,"status":"ok","events":567,"reason":"via http://127.0.0.1:8099"}
entry: "### DS4 tensor split: one dispatch line, all three topologies pass ..."   validity: OK
```

Rejected the bad host, fell through, wrote a good entry, and the beat records which host actually
served it. Run against scratch state and a scratch diary so live state was untouched.

## Which model produced the `////` — and what actually happened to it

Mark's guess was DS4-Flash or Flash-Next, the two models being broken with tensor split that day.
**Neither.** The ledger's endpoints on 2026-08-27/28 were:

| endpoint | model | window |
|---|---|---|
| `.194:8086` (first) | `Qwen3.8-27B-Q6_K` — `argus_stock27b_8086.log` | exited **08-27T23:29** |
| `.194:8084` | `Carnice-V3-Q6_K` — `argus_carnice_8084.log` | exited **08-27T23:29** |
| `127.0.0.1:8090` (last) | **`Ornith-1.5-9B-AD-Q8_0-Q6_K`** — `ornith_restart2.log`, desktop | **08-28T01:50 -> 18:37** |

### Correcting my own first pass

I initially attributed **all six** `////` entries to the Ornith server. Wrong: it did not exist
until 08-28T01:50, so the **08-27 21:11 and 08-28 00:11** entries predate it. At 21:11 both `.194`
servers were still alive, so that one plausibly came from `8086`. The 00:11 entry falls in a gap
where no identified endpoint was up, and remains unattributed.

The error came from parsing the log's elapsed prefix as `HHH.MM.sss.uuu`. It is
**`MMM.SS.mmm.uuu`** — verified against consecutive `print_timing` lines exactly 3.00 s apart
(`976.29.533.673` -> `976.32.550.265` = +3.0166 s). The server's "373 hours" of uptime was
really 6.2 hours, and every wall-clock mapping built on it was wrong. Anchoring elapsed 0 to
`mtime - last_elapsed` gives real timestamps.

### The degradation, which is unambiguous

Mark: *"I'm pretty sure that server degenerated overnight, and failed 6/8 of the runs. Only the
first 2 passed."* Confirmed on substance. Same server, same model, same large-prompt class:

| window | large-prompt requests | behaviour |
|---|---|---|
| 02:12 – 03:57 | **68** | healthy — generations 88 to 10,832 tokens, all terminating normally |
| **04:28, 05:04, 05:33, 06:04** | 4 | **runaway to 65,536 tokens**, the context cap, ~27 min wall clock each |
| 09:49 – 18:07 | 4 | every one pins at exactly **2048**, the ledger's `max_tokens` |

Nothing recovers after 04:28. The transition is sharp and monotonic — a healthy window under two
hours long, then permanent degeneration.

Exact tally on this server: **7 ledger runs, 1 clean (03:07), 6 garbage.** The "first two passed"
memory holds because the two earliest garbage entries came from a different endpoint.

### The mechanism is server lifetime, not model capability

Ornith-1.5-9B served 68 large-context requests cleanly and then stopped recovering. That is a
**server-lifetime** failure, the same shape as AFM-26 (~100x silent degradation measured against
uptime), not evidence about the model. Corroborating instability in the same period:
`ornith_restart.log` records a *failed* load five minutes before the successful one —

```
E llama_model_load: error loading model:
    vector::_M_range_check: __n (which is 1) >= this->size() (which is 1)
```

Not established: **why** it degenerates. The same server logs
`VBR budget ... exceeded with the degrade order clamped at the --vbr-floor` 69 times across its
life, but those warnings do not cluster at 04:28, so nothing here links them.

### The finding that outranks the culprit

The ledger had been summarising full days of engineering work with a **9B model on the desktop**,
because it was third in a fallback list and the first two were dead. Nobody chose that. Even the
runs that were not slashes were capped by a model nobody would have picked for the job.

That is the real argument for the endpoint reorder — not that `.194` is unreliable, but that
"whatever answers first" was never a model-selection policy. And a server that has been up long
enough can fail this way regardless of which model is behind it, which the health check cannot
see.

## Open

- ~~The `////` sections remain in the vector index~~ **Resolved.** `ledger_index.py` now
  classifies each section before indexing, skips malformed ones, and **explicitly deletes** any
  that were indexed earlier (skipping alone is not enough — ids are upserted, so a section
  indexed while it was still considered good would persist forever). Purged 7, collection
  254 -> 247. The files keep them as history; the vector store no longer returns them.
- A bug found while doing that, worth recording: `sections()` returns the body **including** the
  `## HH:MM` header while `ledger_run.sh` strips it, so `classify`'s first-line checks were
  testing the header and could never fire. A raw-reasoning section was indexed as clean even
  after the checker existed. Fixed by normalising a leading heading inside `classify` itself
  rather than at one call site.
- Still unidentified: *why* a 9 B model emitted 2048 tokens of `/`. The same server logs
  `VBR budget ... exceeded with the degrade order clamped at the --vbr-floor` 69 times over its
  life, which is a plausible mechanism worth a controlled test, but the warnings do not cluster
  in the garbage window and nothing here establishes a link.

---

## Follow-up 2026-08-30: acceptance-bar item (2) is now met, and it found a false alarm

The watch-period bar included *"deliberately break it and confirm BOTH observers report."*

- **Human path** — verified earlier: `ledger_notify.sh` alerted on the malformed entry.
- **Agent path** — **verified, and it was already working.** `apollo-diagnostics.timer` fired at
  06:30 today, `run_diagnostics.sh:41` called `ledger_health.sh`, and the result was written into
  `DRIFT_WARNING.md`. I had assumed this channel was dead because `apollo-ctl.sh` is stale; that
  was the wrong evidence — the timer runs `run_diagnostics.sh` directly.

**But it escalated a false positive.** The warning read *"Ledger status `idle` and no successful
entry for 12h. Reason: only 1 new events since line 89320."* That is the ledger working correctly:
nothing happened overnight, so it wrote nothing. `ledger_health.sh` now excludes `idle` from that
branch — a genuinely stopped ledger is still caught by the heartbeat-age check above it.

Worth stating why this matters more than it looks: `DRIFT_WARNING.md` is the one channel agents
are required to resolve at session start. A channel that cries wolf gets ignored, and an ignored
channel is how an 8-week-stale warning sat unread in this repo before. A false alarm in the
alerting path is a defect in the alerting path.

`DRIFT_WARNING.md` cleared, with both entries recorded as resolved rather than deleted.
