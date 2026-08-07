# Pre-registration — DS4-Flash REAP K160 (jabbatheduck/DeepSeek-v4-flash-mini)

**Logged 2026-08-07 ~12:05, in the window between asking jabba what he calibrated on and
receiving his answer.** Nothing has been downloaded and no inference has run. The calibration
prediction below is scorable by his reply alone, which is why it is being written now rather than
after.

## The artifact

`jabbatheduck/DeepSeek-v4-flash-mini`, single 57.3 GB GGUF:
`DeepSeek-V4-Flash-REAP-IQ2XXS-w2Q2K-AProjQ8-OutQ8-chat-v2.gguf`

From the card: **REAP K160 — 160 of 256 routed experts retained = 37.5 % pruned**, top-6 routing
preserved, router and indexer remapped to retained expert IDs. Quantization is hand-mixed:
`IQ2_XXS` routed-expert gate/up, `Q2_K` down-proj, `Q8` attention-proj and output. Card states
**no calibration dataset and no benchmark numbers of any kind.**

This stacks *both* mechanisms our campaign has been trying to separate — 37.5 % expert pruning
**and** ~2-bit weight quantization — in one artifact.

## Predictions (§8)

| id | prediction | confidence |
|---|---|---|
| **P-J1** | jabba's calibration set is predominantly **code/agentic** (REAP-tooling default, evol-codealpaca-like, SWE trajectories) rather than general-purpose or knowledge-inclusive | 0.70 |
| **P-J2** | if P-J1 holds and IKP is run: K160's committed T1 accuracy falls **below** the GLM-REAP-25 % arm's 56.7 % | 0.65 |
| **P-J3** | K160's IKP refusal rate exceeds **50 %** (GLM-REAP-25 % hit 61.3 %) | 0.55 |

**Reasoning for P-J1, stated before the answer:** the REAP reference implementation ships a
code/agentic calibration recipe, community re-prunes typically take author defaults, and jabba's
public work on DS4-Flash is coding-oriented (OpenCode, tool-calling). The prediction is about what
is *conventional*, not a judgement about the model.

---

## RESOLUTION (2026-08-07, same day) — provenance corrected, P-J1 scored

**The prediction was mis-targeted and that is on me.** jabba did the **quantization**, not the
pruning. The prune is `0xSero/DeepSeek-V4-Flash-0731-REAP`; jabba's card credits it as source model
with "quantization inspiration: antirez/deepseek-v4-gguf". "jabba's calibration set" presupposed
something false, and he had no reason to have that answer.

**P-J1: HELD**, scored against 0xSero's card. Calibration was `partial-v2-21289` — 21,289 rows of
*"coding, math, science, tool calling, and agentic tool trajectories."* Broader than the
"code/agentic" wording implied (math and science are present), but **containing no factual or
knowledge component**, which is the load-bearing part. Scoring it HELD rather than partial because
the prediction's operative clause was "rather than general-purpose or knowledge-inclusive," and it
is neither.

### Two facts from the card that were not anticipated

**1. The expert rankings were not computed on these weights.** 0xSero states the rankings were
transferred from a prior checkpoint snapshot (`partial-v2-21289`) and that this is explicitly
*"not a fresh observation of the `0731` weights."*

This is a **second, independent failure mode** stacked on calibration composition: even granting
that the calibration set determines *which capabilities* survive, transferred rankings assume
expert importance is stable across checkpoints. If it is not, the pruner may have removed experts
that were low-salience in the old checkpoint but load-bearing in `0731` — damage uncorrelated with
any calibration set. **This is a hypothesis raised by reading the card, not a pre-registered
prediction, and is marked as such.** It is not scoreable here and would need a fresh-calibrated
control to test.

**2. The author already says this needs measuring.** From the card: *"Structural and smoke
validation do not establish benchmark parity with the unpruned model"* and coding preservation is
*"plausible because coding and agentic data were included, but must be measured rather than
assumed."*

That is this campaign's thesis stated by the pruner himself, unprompted. It also changes the
posture entirely: measuring this is **responsive to a stated request**, not an audit of someone who
claimed something we intend to disprove. 0xSero has claimed nothing and flagged the gap honestly.

### What this does to P-J2 / P-J3

Both stand as written and remain unrun. But note the confound they now carry: K160 combines
**37.5 % pruning + ~2-bit quantization + rankings transferred from a different checkpoint.** A
knowledge deficit could come from any of the three. The unpruned DS4-Flash `UD-IQ1_S` control
isolates quantization; nothing available to us isolates transferred-vs-fresh rankings, so that must
be stated as an open confound in any result rather than resolved.

**P-J2/P-J3 are conditional and currently unrunnable** — see the blocker below. They are logged now
so they cannot be tuned after seeing either jabba's answer or any data.

## The blocker, and the control that has to come first

Neither node can host it as-is:

| node | memory | disk free | verdict |
|---|---|---|---|
| `.194` quad-P100 | 60 GB RAM + 64 GB VRAM | **56 GB** (94 % full) | needs ~5–10 GB freed |
| `.73` dual-P100 | 15 GB RAM + 32 GB VRAM = 47 GB | 61 GB | cannot hold 57.3 GB |

**More importantly, a K160 number alone would be uninterpretable.** DS4-Flash is a different base
model with different baseline knowledge than GLM-4.7-Flash, so "K160 scores X on IKP" attributes to
nothing without an unpruned DS4-Flash arm at comparable quantization.

We already have one: `DeepSeek-V4-Flash-0731-UD-IQ1_S` is resident on `.194` and has **never had IKP
run against it.** That control is:

- **free of any download**, unlike K160
- **cheap** — IKP is short prompts and ~5-token answers, unlike BFCL, whose full tool schemas made
  the DS4 leg prefill-bound at 85 h for 400 items
- a **prerequisite** for any K160 comparison to mean anything
- independently useful — it would be the first knowledge-axis measurement on DS4-Flash at ~2 bits

Quant parity is imperfect either way (ours uniform UD-IQ1_S ~2.32 bpw vs his mixed
`IQ2_XXS`/`Q2_K`/`Q8`) and must be stated in any result. The comparison is prune-vs-no-prune on one
architecture at broadly similar bit budgets, not a matched pair.

## Interpretation, fixed in advance

- **P-J1 holds, P-J2 holds** → the GLM finding generalizes across model, pruner, and ratio, and
  survives being stacked with aggressive quantization. The strongest version of the campaign claim.
- **P-J1 holds, P-J2 fails** → 37.5 % pruning does *not* cost more knowledge than 25 % did on a
  different model. Either the effect is model-specific or ratio is not the governing variable —
  both worth knowing, and both undercut a naive dose-response reading of the planned ladder.
- **P-J1 fails** (he calibrated on something broad) → the most interesting outcome. A REAP whose
  calibration set is *not* code-only is the natural test of whether calibration composition, rather
  than pruning per se, is what determines the damage profile. That is the campaign's stated
  mechanism and nobody has varied it.

## Standing constraint

This is another person's work, shared in a community Mark participates in. Any measurement is
offered to jabba first and is his to contextualize; the campaign's finding is about *undisclosed
calibration sets* as a general practice, not about his model specifically. Nothing gets published
without his awareness.
