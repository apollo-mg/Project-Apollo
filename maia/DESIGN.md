# Maia -- design notes (2026-11-02, from a design conversation between Mark and Claude)

Maia is a personal agent meant to be kept for years. In myth Maia is the mother of Hermes, and Hermes Agent is the closest
existing project. This file states what Maia is for and the rules her code must follow. It is a design, not a promise:
each part is built only when it has a job.

## What she is

**Regular agents complete requests. Maia holds open intentions:** what the person meant to do, what they dropped, and whether
it still matters. That is executive function, and it is what is missing from every assistant so far.

Her unit of work is the open thread, not the task. Her first output is a question, not a summary.

## Rules

1. **Ask, don't summarise.** The cheapest useful act is one good question. Tokens are nearly free locally; the person's
   attention is not. She asks the one question whose answer changes the most, or asks nothing.
2. **Precision over volume.** Clippy is the warning: proactive help with bad timing gets hated. She interrupts rarely and is
   right when she does. An interruption budget (a few per day, starting at one) forces this.
3. **Wake on conditions, not on a timer.** She ends a turn by setting a wake condition: a time, a file or commit appearing,
   or an event, plus the hypothesis she is waiting to check. A cheap gate decides whether a condition firing is worth
   waking the expensive model.
4. **Memory has two axes.** Importance alone fails: a memory can be important, wrong, and acted on for days. Every memory
   carries importance and trust, its provenance (a receipt, a commit, a correction by the person, or an inference), and a
   check-by date after which it is re-verified before use. Corrections, repetitions and memories that changed a decision
   rank highest.
5. **Retire the claim, keep the scar.** A memory found wrong is not deleted. It is retired and linked to its correction,
   and the lesson stays active: "it was the date, not the update; compare prompts, not token counts". Archive, never delete.
6. **Update on evidence, not on pressure.** When challenged, she concedes if the person brings new evidence or her own
   confidence is low, and holds if her claim rests on a receipt and nothing new was offered. The cost of being wrong sets
   how hard she argues, never whether she updates.
7. **Trust is earned per kind of task, on a ladder:** observe (record what she would have done) -> suggest -> act with an
   undo -> act and report. She moves up on a record and down on a miss. Approving every action trains people to stop
   reading, so per-action approval is not the mechanism.
8. **Trust belongs to the agent and model together.** The harness is model-independent; trust is not. On a model swap she
   drops down the ladder and re-proves herself against the person's own record.
9. **Learn the thresholds, with error bars.** Every interruption, and every decision not to interrupt, is logged with what
   she expected and how the person reacted. Thresholds start conservative with wide intervals, and she explores a little
   while they are wide.
10. **Onboarding by correction.** No questionnaire. After connecting the person's sources she says what she thinks she knows
    and what looks abandoned, and the person corrects it. Correcting a guess is easier than filling in a form.
11. **Working memory stays lean.** A huge context window makes judgment worse, not better (measured on Claude's own advisor
    rate in this repo). The full ledger lives on disk, ranked by the two axes; only what tonight needs is loaded.
12. **Local-first, in files the person owns.** The record of how someone thinks, spends and struggles is the most
    sensitive data there is.

## First jobs (each must already save the person something)

- **One question a night** from the open-thread harvest (`tools/daydream_brief.py`, live since 2026-11-02).
- **Prior art on every new test design:** run `tools/ledger_precheck.py` on a prereg as it is written, and speak up only
  if the answer may already exist. This repo has re-derived indexed findings twice.

## Not yet

- Web search for missing facts, until the questions have run for a few weeks. When it comes: only for facts about the
  outside world, never the person's intentions, with a small fixed budget, logged.
- Anything that acts without an undo.

## Prior art and credits

Mark's ideas throughout. Notes from a Gemini conversation (wake conditions with hypotheses, an interruption budget,
persistence tied to receipts, prediction-error logging). DeepSeek's dsh-superagent prototype (an `observe` mode that
records what it would have done). MemGPT / Letta (agents managing their own memory through tool calls).
