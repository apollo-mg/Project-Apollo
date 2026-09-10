# Four harness generations in one day — every defect blamed the model

**2026-09-02.** No model result from this corpus is reportable yet. What follows is the record of
building the instrument, kept because the failure pattern is the transferable part.

## The generations

| gen | design | defect | how it presented |
|---|---|---|---|
| v1 | regex -> whole captured file | no state transitions; a rebuild replayed the same error forever | "model failed to self-correct" |
| v2 | + edit state machine (`replay_stateful.py`) | still returned whole files; `sed -n '444p' \| wc -c` got 1700 lines | "model looped degenerately, 11 identical turns" |
| v3 | + real execution (`replay_exec.py`) | kernel header pointed at pre-filtered **grep output**, not the file; `ls` refused | "model answered without checking" |
| **v4** | + real 588-line `string.h`, `ls` support, calibration gate | — | — |

Plus two runner defects: `max_tokens=2048` starved a reasoning model into emitting no content
(the identical bug fixed in `ledger_build.py` three days earlier and not carried over), and
`-c 8192` overflowed on a multi-turn loop.

## The pattern

**Six defects, six times the model looked worse and the harness looked fine.**

That asymmetry is structural, not luck. The model is the scored object, so any fault in serving,
starving or grading lands in its column by default. Nothing reports "the instrument failed" unless
a channel is built for it. Every one was found by **reading transcripts**, never by looking at a
score — a score cannot distinguish "model is confused" from "model is being fed noise".

The worst instance: the 27B was recorded as "degenerate looping, same family as the ledger `////`".
It had asked `sed -n '444p' ... | wc -c` and been handed the file's opening lines. It tried `od`,
`xxd`, `wc -c` — four phrasings of the same precise question — and got the identical irrelevant
blob each time. At temperature 0 there is no escape from that. **Any model loops there.** It was
recorded as a model pathology and it was mine.

## The gate that would have caught nearly all of it

`calibrate.py` replays **Claude's own known-good command sequence** and asserts each step returns
what Claude actually saw, including the `444 -> 445` displacement that is the item's whole
discriminator. It takes under a second.

Had it existed first: v1 fails (rebuild returns 444 twice), v2 fails (`sed -n '444p'` returns
SPDX header), v3 fails (`grep -E '^char \*strncpy'` on the header returns grep output, not
nothing). All three caught before a single model call.

**Rule, now in `DESIGN.md`: a failing gate voids the item, not the model.** It is the control arm
for the instrument, and it is the same discipline these receipts demand of every hardware
measurement in this repo.

## An artifact worth remembering

On the **broken** v2 harness Flash-Next performed *better* — it applied the wrong fix, rebuilt,
caught the displacement, and went to the kernel headers. On the corrected v3 it answered in 8
turns without ever rebuilding. Plausibly the broken harness's noise forced exploration that the
clean one did not.

A worse instrument produced better-looking behaviour. That is the precise reason benchmark numbers
without transcripts are untrustworthy, and it argues for keeping full transcripts permanently
rather than scores.

## Status

- v4 harness: calibration 9/9, real header, `ls`, executing read-only commands against captures.
- All v1/v2/v3 runs moved to `voided/` with the reason recorded per run.
- v4 runs in progress, K=2 per model. **Nothing publishable until those land and are read line by
  line rather than scored.**
