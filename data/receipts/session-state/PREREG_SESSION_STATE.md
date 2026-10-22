# PREREG -- Can a local memory writer carry a session across compaction as well as Claude Code's own summary?

**Registered before any arm is scored.** Code frozen at `67328fda` (`tools/session_state.py`,
`tools/session_state_eval.py`). Dev tuning used only the live slice after compaction boundary 87 (never scored).

**Prior art checked:** `ledger_precheck.py "session memory compaction transcript state writer"` -> incidental matches
only (INDEX L305 advisor decays with context; L333 a 4B fails HermesAgent's stateful memory tasks); nothing here has
measured compaction or memory writing.

## Question

Claude Code compacts a long session by writing one summary at a token threshold. This project's main session has
been compacted 88 times since 2026-07-02. The sidecar (`session_state.py`) instead has a local model write short,
cited memory items per transcript slice, and the code keeps only what it can verify. Does it carry the session's
facts as well as the built-in summary at the same size, and does a model trained for memory writing (Tencent
Hy-Memory-30B-A3B) do better than the general model already serving on .73? And does the quant matter?

## Units and gold

- **Segments 75-87** of the main session transcript: segment k is the transcript between compaction boundaries k-1
  and k (`segments` asserts that summary k directly follows boundary k). Writers start each segment from an empty
  state.
- **Gold** (mechanical, chosen by no arm and no judge): (1) the subject line of every commit made in the segment's
  time window that has a Claude co-author trailer; (2) sentences of Mark's that match the directive regex, excluding
  pastes of other people's chat; (3) the description, or first sentences, of every memory file written in the segment.
  Key tokens per item: numbers (2+ digits or decimals, not years), path/file/identifier-shaped tokens, CAPS
  identifiers, hashes, minus a registered stop list of generic words. Items with fewer than 2 keys are not scored;
  items matching the personal deny list are excluded (the sidecar is designed not to keep them).
- As built: **139 scored items** (commit 102, memory 34, directive 3); segments 82 and 85 contribute none.
- **Carried:** at least half of an item's keys occur as whole tokens in the arm's text, after removing the sidecar's
  citation and `[unverified]` markers.

## Arms

| arm | what |
|---|---|
| INC | Claude Code's compaction summary k (the incumbent), as written into the transcript |
| EXT | no model: the newest redacted HUMAN and SAY lines of the segment, cut to the budget |
| QW27a, QW27b | `session_state.py` with Qwen3.8-27B, the .73 daily driver via the wake proxy, `enable_thinking: false`; run twice, because the daily (VBR, np 2, MTP) is bistable |
| HY4 | `session_state.py` with Hy-Memory-30B-A3B Q4_K_M imatrix (Tencent's GGUF, sha256 `e417fc86...`), .194 4x P100, llama.cpp `f74e2fa`, `-sm layer -np 1 -c 32768`, F16 KV, `reasoning_effort: no_think` |
| HY8 | the same with Q8_0 (sha256 `3ba2897d...`), loaded from `/dev/shm` |

Budgets: every arm except INC is rendered at 0.5x, 1x and 2x INC's length for that segment. **Primary: pooled recall at
1x.** Differences by paired bootstrap over items (10,000 resamples, 95% CI).

## Gates (instrument validity, checked first)

- **G1 chance:** each arm's text scored against a different segment's gold. If any arm's chance recall at 1x exceeds
  0.15, the key-token metric is too loose and every comparison below is descriptive only.
- **G2 identity:** before HY8 is treated as a quant of HY4, the two files' GGUF metadata must agree on the checkpoint
  (their names differ: `Hy-Memory-Step250` vs `hy3a3b-memrl1009-step250`). If they do not, HY8 is a separate model.
- **G3 determinism:** HY at np 1, temperature 0 gave byte-identical states on two runs of the dev slice; this is
  re-checked on one test segment.

## Predictions

| # | prediction |
|---|---|
| P1 | INC carries more than EXT at 1x (a summary beats raw recency) |
| P2 | every model writer carries more than EXT at 1x |
| P3 | the best model writer is within 0.05 of INC at 1x, or above it |
| P4 | HY4 carries at least as much as QW27 (mean of the two runs) at 1x |
| P5 | HY8 and HY4 differ by at most 0.05 at 1x. Same prompts (HY4's saved prompts sent to HY8): identical ops on fewer than half of the prompts, word Jaccard of the op texts at least 0.5 |
| P6 | no personal-category content in any writer's output, after reading every deny-list hit (INC's hits are reported, not predicted) |

## Known biases, stated now

- INC also carries older material (summary k-1 was in its context), so part of its budget is spent outside segment k;
  writers spend all of theirs on segment k. This favours the writers.
- The gold is mostly commit subjects, which are dense with numbers and names; the metric rewards keeping specifics
  verbatim, which is the sidecar's design goal and not necessarily what a summary optimises.
- Items are clustered in segments 86 and 87 (83 of 139).

## Privacy

Gold, arm texts and per-item scores contain private session content and stay in
`~/.local/share/apollo/session_state_eval/` (local). Only aggregate numbers are committed.

## Addendum 1 -- Recursive Flint as a writer (registered 2026-10-21, before any Flint row)

**Prior art checked:** `ledger_precheck.py "Flint session state memory writer instruction following"` -> this
instrument's own result (`RESULT_SESSION_STATE.md`); nothing on Flint. **What this adds:** a fourth writer, chosen
because its published strength is instruction following (IFBench 89.2), the failure seen in the registered arms (Hy
ignored "one fact per item" and never landed an UPDATE; the 27B misread one item).

- **Arm FL8:** Recursive Flint (40B total, 2.5B active, `FlintForCausalLM`, Apache-2.0, released 2026-10-21),
  Unsloth `flint-Q8_0.gguf` (sha256 `5df42b56859c7b51...`, verified before use), on .194 4x P100 at the HY arms'
  placement (`-sm layer -np 1 -c 32768`, F16 KV), fresh upstream llama.cpp build (the registered `f74e2fa` predates
  Flint support; the build commit is recorded in the result). Thinking off by whatever switch its template exposes
  (recorded); greedy, as all arms.
- **Same writer code as the registered arms:** `session_state.py` at `67328fda`, pinned via `SESSION_STATE_PY`
  (later fixes to update ids and number marking are NOT used, so FL8 is comparable to HY4/HY8/QW27).
- **Same gold, scorer, budgets and analysis** (`analyze` at `2fa436cf` + Deviation 1's pairing key). G1 already failed
  for the registered arms, so FL8's comparisons are descriptive too. G3-style determinism: segment 80 run twice.

| # | prediction (descriptive) |
|---|---|
| F1 | FL8 carries at least as much as HY4 at 1x (within -0.05) |
| F2 | FL8 lands more UPDATEs than Hy's zero (instruction following) |
| F3 | FL8 at the 27B's length per segment carries more than the 27B (selection, not volume) |
| F4 | no personal-category content in FL8's output |
