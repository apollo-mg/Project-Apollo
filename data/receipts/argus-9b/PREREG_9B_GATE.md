# Prereg — can the argus instrument see a 9B at all?

**Written 2026-09-22, before any arm ran. This is a GATE, not the panel.** It decides whether a
5-rep MiMo-vs-Ornith comparison is worth its hardware, and it measures the resolution limit at the
sampling each model actually requires.

**Prior art checked:** `ledger_precheck.py "MiMo distill 9B agentic smoke test small model floor"
--deep` -> `argus-v2/RESULT_NOISE_FLOOR.md` (the 10.3 % floor), `FINDINGS_2026-08-25.md` (the v1
corpus had almost no discriminating power), `viability/RESULT_SPARK4B_TOOLS.md` (a 4B scores 24/24
on tool-call mechanics, which is not agentic competence), `FAILURE_MODES.md` AFM entry on Ornith
looping when given its coding profile.
**What this adds:** every prior argus figure is temp 1.0, single rep, on a 27B. Nothing measures
whether a **9B** lands in the corpus's measurable band, and nothing measures the noise floor at any
temperature **other than 1.0**. Both are prerequisites for the panel and neither is published.

## Why a gate and not the panel

`RESULT_NOISE_FLOOR.md`: two identical arms disagree at **10.3 %** at temp 1.0, one rep --
*identical to the "signal"* measured between two different quants. The panel costs 5 reps x 2 arms.
Before spending that, two things must be true, and neither is known:

1. **The 9Bs must land in a measurable band.** If either floors or saturates on 31 scorable items,
   there is no variance to compare and reps cannot create any.
2. **The floor must be known at the sampling these models require** -- which is not temp 1.0 for
   MiMo.

## The sampling problem, stated plainly

Under the standing rule that manufacturer sampling is the only proper configuration, the two arms
are **not sampled alike**, and the difference is large:

| | temp | top_p | top_k | min_p | presence |
|---|---:|---:|---:|---:|---:|
| **Ornith-1.5-9B, "general"** (the agentic profile) | **1.0** | 0.95 | 20 | 0.0 | **1.5** |
| Ornith-1.5-9B, "precise coding" (NOT used -- it made Ornith loop on every scenario, 08-28) | 0.6 | 0.95 | 20 | 0.0 | 0.0 |
| **MiMo-V2.6-Distill-Qwen-9B** (only published profile) | **0.6** | 0.95 | 20 | *unspecified* | **0.0** |

`min_p` for MiMo is **our choice, pinned to 0.0**, because the card is silent and llama.cpp would
otherwise supply 0.05 (`AFM-23`). Recorded as ours, not the vendor's.

**Therefore this experiment cannot answer "does agentic SFT buy judgement."** Temperature and
presence penalty both differ by vendor instruction, so any measured gap is
model + sampling, inseparably. What it *can* answer is **"MiMo as shipped vs Ornith as shipped"** --
the comparison a user actually faces. The prereg commits to that framing; the receipt must not
drift from it.

**All sampling is pinned explicitly on the command line** per `AFM-42`: MiMo's GGUF embeds
`general.sampling.temp 0.6 / top_k 20 / top_p 0.95` and Ornith's embeds nothing, so identical
launch flags would otherwise have produced different temperatures silently.

## Arms

RX 9070 XT (gfx1201), upstream llama.cpp build 11095 (`58367713a`) `build_rocm`,
`-ngl 99 -c 8192 -fa on -ctk f16 -ctv f16 -np 1 --kv-unified`. **No MTP head** (see below).
`families_v4.json`, 40 items / **31 scorable** (9 are gate role). 1 rep. Sequential -- two 9.5 GB
models do not co-resident on 16 GB, and `-np 1` is required
(`[[agent-benchmark-determinism]]`: concurrent batching was itself a nondeterminism source).

| arm | model | sampling |
|---|---|---|
| `MIMO-a`, `MIMO-b` | MiMo-V2.6-Distill Q8_0 | temp 0.6, top_p 0.95, top_k 20, min_p 0.0, presence 0.0 |
| `ORN-a`, `ORN-b` | Ornith-1.5-9B Q8_0 | temp 1.0, top_p 0.95, top_k 20, min_p 0.0, presence 1.5 |

Each model runs **twice under identical configuration**. The a-vs-b discordance is that arm's
**noise floor at its own sampling** -- the same design as `RESULT_NOISE_FLOOR.md`, which is the only
reason we know the 27B figure.

**MiMo uses `argus/templates/mimo_v26_distill_qwen9b_autoparser.jinja`.** Mandatory, not optional:
the stock template corrupts 17/30 multi-tool-call turns, and while **zero** corpus items *expect*
2+ actions, **304 of 350 scenarios in the live Hemmingway run make 2+ backend calls**. The
corruption folds a second call into the first one's argument, which would silently convert an
over-action (`WRONG-ACTION`, the thing we score) into an apparent single clean action.

## Predictions, committed before data

| id | prediction | conf | falsifier |
|---|---|---|---|
| **G1** | both models land in 20-80 % pass rate (the measurable band) | 0.45 | either floors <15 % or saturates >85 % |
| **G2** | MiMo's noise floor at temp 0.6 is **below** the 27B's 10.3 % at temp 1.0 | 0.75 | >= 10.3 % |
| **G3** | Ornith's noise floor at temp 1.0 is within +/-4 points of 10.3 % | 0.60 | outside |
| **G4** | the MiMo-vs-Ornith pass-rate gap is **smaller** than the larger arm's own noise floor | 0.55 | gap exceeds it |
| **G5** | neither arm produces a `SUSPECT` rate above 10 % | 0.70 | either exceeds |

**G4 is the decision.** If the between-model gap does not clear the within-model noise, the panel
cannot resolve these two models and should not be run at 5 reps -- the honest output is a bound
("no difference larger than X"), not a comparison.

**G1 at 0.45 is deliberately low.** A 9B on a corpus built to separate 27Bs is more likely to floor
than not, and that would be a clean, cheap negative worth publishing on its own.

## Deliberately excluded

**No MTP head in the instrument.** The Ornith head is a base-family asset and would roughly double
throughput on this tool-call-heavy corpus, but `RESULT_MTP_HEAD_TRANSFER.md` established that
speculation changes emitted text. Adding a drafter to a measurement rig adds an axis. It is instead
its own follow-up, below.

## Follow-up this gate enables (Mark, 2026-09-22)

> *"does enabling MTP cause any errors that don't happen without"*

Better posed than a throughput question, because argus has a **typed verdict space**
(`CORRECT` / `WRONG-ACTION` / `WRONG-INACTION` / `CLARIFIED` / `INFRA` / `SUSPECT`). So the question
is not "does the rate move" but **"does speculation introduce verdict classes that are absent
without it"** -- and it is a paired, same-item design, analysable with the McNemar machinery already
in `tools/discordance.py`.

It needs this gate first: a model that floors or saturates cannot show a class shift either. Run it
as `MIMO-mtp-a/b` against `MIMO-a/b`, same sampling, head on/off the only difference, and report
the **verdict transition matrix**, not the aggregate.
