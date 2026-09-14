# Design note — the ledger records *why*; it does not verify *still true*

**Written 2026-09-14.** Motivated by Mark sharing
[*Coding Agents Don't Need Longer History, They Need Intent Continuity*](https://towardsdatascience.com/coding-agents-dont-need-longer-history-they-need-intent-continuity)
(Towards Data Science), and by four failures in the same session that the article predicts.

## The article's argument, in its own terms

**Intent continuity is carrying an old requirement into a new task without the user repeating it, while
dropping that rule if something newer overrides it.** The author's central claim is that this is **not a
retrieval problem and not a context-length problem — it is a validation problem.** An agent holding the
entire history still fails, because a requirement stated 60 messages ago and never repeated never gets
connected to a new task that does not mention it. Their worked example: "never expose database IDs", stated
early, silently violated later when building an auth flow.

Their proposed pipeline: **Extractor** (scan for must / never / required) → **Candidate Retrieval**
(a hand-written domain schema, not keywords) → **Verification Layer** (is this rule superseded? does it
apply to this scope?) → **Compiler** (flatten to key-value context) → **Checker** (grade against ground
truth).

**The result is the part worth stealing:** across 8 tasks, no-history failed all 8, keyword retrieval passed
4 of 8, and retrieval **plus verification** passed 8 of 8 — recovering 100% of required fields against
keyword retrieval's 57%. **The verification step is where the gain is**, not the retrieval.

## What Apollo already has

`tools/LEDGER_SPEC.md` states the same thesis independently, and earlier: *"Reasons, not events. Receipts
capture results; what gets lost at every compaction is why — which is what stops work being redone."* Its
extractor deliberately targets decision points: errors, commands repeated three or more times (something was
fighting back), **short human turns following assistant prose** (corrections and redirects), and artifacts
touched.

Mapped onto the article's pipeline:

| article component | Apollo | state |
|---|---|---|
| Extractor | `ledger_extract.py` + the skeleton pattern | **built**, healthy (`ledger_health.sh`: ok, 0h) |
| Candidate retrieval | `ledger_index.py` / `ledger_query.py`, vector store | **built** |
| **Verification layer** | — | **MISSING** |
| Compiler | memory files + `CLAUDE.md`, loaded per session | partial |
| Checker | preregs + committed scorers | **built, and stronger than the article's** |

**The gap is the one component the article says carries the gain.**

## The evidence: four failures in one session, all verification failures

None of these were retrieval failures. In every case the fact was stored and available; nothing checked
whether it was still true, or whether the thing had actually run.

1. **Stale mutable fact.** Memory said `/mnt/TG_2TB` had **71 GB free**. It has **1.1 TB**. Cleanup planning
   was built on the stale figure until it was measured.
2. **Stale mutable fact.** Memory said `/mnt/nas` is mounted read-only. **It is not mounted at all.** A
   migration target was proposed onto a filesystem that does not exist.
3. **Standing rule not applied.** `CLAUDE.md` forbids `pgrep -f` / `pkill -f` on a pattern you may be inside
   of. `pgrep -f "exl3_kld_arm"` was run anyway, from inside an ssh whose own command line contained that
   string.
4. **A written rule re-broken a third time.** The waiter rule (count markers, compare numerically) is in
   memory with two prior instances recorded; a third variant shipped the same day the rule was rewritten.

Two further cases the same day had the same shape — **a clean result from something that never ran**:
`score_exl3_compression.py` silently dropped an unregistered arm and reported no change; and MTP was declared
unusable because `--spec-type draft-mtp` was never passed, so llama.cpp's *default-off* notice was read as
*capability-missing*. That one nearly became a bug report to bartowski about a non-bug.

## The distinction that would have caught 1 and 2

**Memory currently stores immutable findings and mutable observations with identical authority.**

- *"GP100 has no dp4a"* — a property of silicon. True forever. Cite it freely.
- *"`.194` has 56 GB free"* — an observation with a shelf life measured in hours.

**Proposal: a mutable-state entry carries a measured-on date and is never cited as current — it is
re-measured before use.** One line of discipline, no new machinery. It would have caught the disk figure, the
NAS mount, and the assumption that `.194` was the only host holding the Q8_0 reference — which cost a 27 GB
re-download of a file already sitting on the control plane.

## The distinction that would have caught 3, 4, and the two never-ran cases

**A check that returns a clean result deserves the same scrutiny as a surprising one.** Ask *did this
actually run* before *what does it mean*. Every instance above produced a plausible, well-formed, entirely
wrong answer without erroring — which is exactly the failure mode `readiness-probes-lie` already names for
servers, generalized to rules and scorers.

## Status

Not implemented. Recorded now so the motivation is auditable later, per Mark: *"keep that or something
similar going, along with the article text as the motivation for trying it, so we can reflect back and audit
things easily down the road."*
