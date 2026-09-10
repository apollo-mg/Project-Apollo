# Ledger system — porting spec

An honest account of what transfers, what needs rewriting, and what will bite you. Written
for someone with a different agent harness on different hardware.

## What it does

Periodically turn an agent session transcript into a searchable engineering diary, and make
its own failure visible. Three properties, in order of importance:

1. **Reasons, not events.** Receipts capture results; what gets lost at every compaction is
   *why* — which is what stops work being redone.
2. **Searchable.** A diary you cannot search is one you stop reading, and one you stop reading
   is one nobody notices has broken. Dated files with no index is how our first attempt died.
3. **Self-reporting.** Every run writes an explicit status. Silence is a detectable state.

## The four layers, by porting cost

| layer | files | cost to port |
|---|---|---|
| **A. Pattern** | design only | free — this is the transferable part |
| **B. Config** | 8 hardcoded paths across 7 files | minutes |
| **C. Extractor** | `ledger_extract.py`, 71 lines | **rewrite** — harness-specific |
| **D. Dependencies** | vector store, timers, notifier | swap-in |

### A. The pattern (steal this, not the code)

**Do not ask the model to discover what mattered from hundreds of events.** That is the hard
part and a small local model does it badly. Extract a SKELETON mechanically, then have the
model write reasoning around a structure it did not have to find:

- **errors** — anything that failed
- **repeated near-identical commands** (>=3x) — the "something was fighting back" signal.
  Match on a normalised prefix, NOT on tool name: our first version reported "Bash x130",
  which just means Bash is the primary tool. Zero signal.
- **short human turns immediately following assistant prose** — these are reliably
  corrections and redirects, i.e. decision points
- **artifacts touched**

Then: *"every error, retry loop and human correction exists because something went wrong.
Explain the cause where the events support it. Do not invent causes."*

A 27B local model produced a factually accurate technical diary this way, with no hallucinated
numbers, and independently identified a process failure we had only noted in passing.

### B. Config

`ROOT`, the transcript directory, and an ordered endpoint list. That is all.

### C. The extractor — the only real rewrite

71 lines, zero hardcoded paths, but 100% Claude Code schema knowledge: JSONL where
`type: assistant|user` records carry `message.content` arrays of `text` / `tool_use` /
`tool_result` blocks.

**Contract your replacement must satisfy** — emit one line per meaningful event:

```
HUMAN  <text>                  what was actually asked
SAY    <text>                  assistant prose: conclusions, reasoning, corrections
TOOL   <name>  <arg digest>    what was done
ERR    <first error line>      what failed
```

**Drop tool RESULT bodies.** That is the entire compression: 198 MB → 4.9 MB (40x). A ledger
needs actions and conclusions, not the bytes those actions returned.

Support `--since-line` (or equivalent) and persist the offset. Incremental is not an
optimisation — our predecessor accumulated GBs before summarising and was always fighting a
backlog. Steady state here is ~1,800 events / ~100k tokens per 3-hour window.

### D. Dependencies

- **Vector store**: we reuse an existing Chroma + local `all-MiniLM-L6-v2`. Any store works;
  tag entries with a type field so they can be filtered in or out. Strip skeleton blocks
  before embedding — raw telemetry swamps the prose. Use deterministic ids (`ledger:DATE:TIME`)
  so re-indexing upserts instead of duplicating.
- **Scheduler**: systemd user timers here (`Persistent=true` so missed runs fire on boot).
  cron is equivalent — set `PATH` and `DISPLAY` explicitly or the notifier silently fails.
- **Notifier**: `notify-send` + a MOTD file. Any push channel.

## Monitoring — the part most likely to be skipped, and shouldn't be

**Two observers that share no dependency.**

```
agent path : timer -> diagnostics -> DRIFT_WARNING.md -> agent reads at session start
human path : timer -> notify      -> desktop notification + shell MOTD
```

Different trigger, different sink, different reader. Either can die without silencing the other.

**We have proof this matters.** The agent path here hung off a control-plane script that had
not run since 2026-07-06. A drift warning sat unresolved for **eight weeks**. Auditing that
turned up two more silently-dead subsystems in the same codebase. Every one would have
announced itself within six hours under this pattern.

Statuses: `ok` / `idle` / `degraded` / `error` + reason. `idle` (nothing new) must be distinct
from `error`, or a quiet day looks like a failure. `degraded` (written but not indexed, or no
endpoint reachable) must be distinct from `ok`, or partial failure looks like success.

## Failure modes we hit — expect these

| symptom | cause |
|---|---|
| model returns empty output | reasoning model spent its budget in `reasoning_content`. Raise `max_tokens`, fall back to reasoning text |
| scenario runs for hours under a short timeout | `urllib` timeout is **per-socket-operation**, not total. A trickling SSE stream never trips it. Enforce a **wall-clock deadline** checked per line |
| model loops forever | sampling. Cards often publish MORE THAN ONE profile — we applied a *coding* profile (temp 0.6) to *agentic* work when the card specified temp 1.0 / presence 1.5 for general use. Read `/props`, not your launch command |
| day file becomes unreadable | model emits `##` headings that collide with the run wrapper. Instruct level 3+, AND demote mechanically — prompt compliance is not a contract |
| first run takes forever | it is a full-history pass. Ours was 21,282 events, ~8 min on a 27B **that was sharing GPUs with a live experiment** |

## Known-unsolved

- **Scheduling is time-based, not idle-based.** It will collide with real work. An older
  daemon in this same repo idle-gates on a GPU EWMA and is the better design; not yet merged.
- **No rollup.** Eight entries/day is right for "what happened this afternoon", wrong for
  "what did we conclude this week".
- **Retrieval granularity is per-run.** Finer chunking would discriminate better once there
  are many entries.
- Growth: ~4 KB/run, ~30 KB/day, ~11 MB/year. Size is not the problem; findability was.
