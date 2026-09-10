# TURBO at `reasoning_effort: medium` — the claim fails harder, and cleanly

**2026-09-03.** `.194`, 2x P100 sm_60 @ **150 W / 1063 MHz** (both arms, captured at ready).
`-c 16384 -ngl 99 -fa on --jinja -np 1 -fit off -sm tensor`, `GGML_CUDA_ALLREDUCE=internal`.
Sampling per the model card (= Unsloth's thinking-mode): `temperature=1.0, top_p=0.95, top_k=20,
min_p=0.0, presence_penalty=0.0`, `max_tokens=4096`.

Follow-up to [RESULT_TURBO_THINKING.md](RESULT_TURBO_THINKING.md), which ran at the **default**
effort. Default is `xhigh`, which injects 237 characters of "think carefully, validate key
assumptions, consider plausible alternatives" into *both* models (AFM-23; verified byte-identical
across the two chat templates). `medium` injects **nothing**, so this run exposes trained
behaviour rather than instructed behaviour.

| arm | model | VRAM at ready |
|---|---|---|
| turbo | `DavidAU/Qwen3.8-27B-TURBO-...-NEO-CODER-MAX-MTP-Q4_K_S` (16.33 GiB) | 8375 MiB x2 = 16.75 GiB |
| control | `Qwen3.8-27B-Q6_K` (21.31 GiB) — what `.73` serves | 10747 MiB x2 = 21.0 GiB |

Both loads clean: footprints match model size, no OOM, no memory-pressure fallback, no stray
server resident. Turbo server log shows **5** `slot release` events — all five prompts served.

## Result — `reasoning_content` characters per prompt

| prompt | turbo | control | ratio | xhigh ratio | direction |
|---|---|---|---|---|---|
| factual | 3,509 | 1,095 | **3.20x** | 1.76x | same |
| arithmetic | 4,678 | 646 | **7.24x** | 1.95x | same |
| logic puzzle | 3,508 | 1,634 | **2.15x** | 2.30x | same |
| format (3 bullets) | 938 | 783 | **1.20x** | 1.78x | same |
| no-repeat | 4,856 | 2,794 | **1.74x** | 0.30x | **FLIPPED** |
| **TOTAL** | **17,489** | **6,952** | **2.52x** | 0.92x | |

**Median per-prompt ratio 2.15x. TURBO thinks more on 5 of 5.**

## The finding is the direction, not the ratio

The open question from the xhigh run was whether its result was an artifact of the injected effort
instruction. It was not — **removing the injection makes the effect stronger and unambiguous.**

The xhigh aggregate of 0.92x was carried entirely by one prompt, where the *control* emitted a
5,312-char outlier. At medium the control produces 2,794 chars on that same prompt and the ratio
flips to 1.74x in line with the rest. So the injection was **masking** the effect, not creating it.

Drop-one-out confirms no single prompt carries this aggregate:

| dropped | remaining aggregate |
|---|---|
| factual | 2.39x |
| arithmetic | 2.03x |
| logic puzzle | 2.63x |
| format | 2.68x |
| no-repeat | 3.04x |

Range 2.03x–3.04x, every one far above parity. Contrast the xhigh run, where dropping one prompt
inverted the conclusion. **This is the more trustworthy of the two runs.**

Card claim: *"drastically reduces thinking tokens (by 1/2 to as high as 1/10)."* Claimed 0.5x–0.1x.
Measured **2.52x aggregate, 2.15x median, in the opposite direction, on 5/5 prompts.**

## Quality holds — and it thinks more to say less

All 10 responses `finish=stop`, no truncation, no repetition.

- **Arithmetic:** both correct. TURBO set up `60(t+2) = 90t`; control set up `60t = 90(t-2)`.
  Equivalent, both solved.
- **Format:** both produced exactly three capitalised single-sentence bullets.
- **Content length:** TURBO's *answers* are **shorter** on 3 of 5 (factual 514 vs 660, logic 894 vs
  1,099, no-repeat 1,930 vs 2,884). So it spends 2.5x the thinking to produce a shorter answer.

Nothing suggests the merge or the Heretic ablation damaged the model. The specific headline claim
is simply false in direction, and now with a clean signal rather than an outlier-dependent one.

## What this costs in practice

Total completion tokens: turbo **6,043** vs control **3,326** = **1.82x**. Since wall-clock per
task = tokens x (1/throughput), and this model is not faster, TURBO costs ~1.82x the wall clock of
stock Qwen3.8-27B on the same five prompts. For a throughput-motivated swap that is the whole
verdict: **do not swap.**

## Limits — unchanged from the xhigh run, and they still bind

- **This is "DavidAU's merge" vs "stock Qwen3.8-27B", not "TURBO" vs "no TURBO".** The medium run
  moves the *instruction* variable only; the *model* confound is untouched. Isolating the TURBO
  treatment requires DavidAU's non-TURBO build of the same merge. A negative result here cannot
  distinguish "TURBO does nothing" from "TURBO helps but the merge costs more than TURBO saves."
- **Quant unmatched** (Q4_K_S vs Q6_K). Should barely affect thinking *length*, which is
  behavioural, but it is not controlled.
- **5 prompts, K=1.** Existence proof, not a rate. Mitigated but not removed by the drop-one-out
  check above.
- **No pre-registered prediction for this run.** The xhigh run had
  `PREDICTIONS_turbo_thinking.md`; this follow-up did not, so nothing here is prediction-scored.
  Stated in advance only as "the finding will be the direction change, not the raw ratio."

## Harness note

The first attempt at this run produced a valid turbo arm and a control arm that died on
`couldn't bind HTTP server socket, port: 8096`. Cause: `pkill -x llama-server; sleep 2` + `sleep 4`
gives llama-server ~6 s to shut down, and releasing 16.75 GiB of VRAM takes longer, so the port was
still bound. Also `kill -0 $!` after `setsid` is meaningless — setsid forks and exits, so the probe
reported "died" for a healthy server. Both fixed by polling postconditions
(see [RESULT_BATCH_PARALLELISM.md](RESULT_BATCH_PARALLELISM.md)).

## The claim was never quantified by its author

Checked both cards on 2026-09-03 -- the GGUF repo
(`...-NEO-CODER-MAX-MTP-GGUF`) and the now-ungated source repo
(`DavidAU/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NM-DAU`).

**Neither card contains any quantified thinking-token measurement.** The source card's benchmark
tables report arc/c, arc/e, boolq, hswag, obkqa, piqa, wino -- accuracy only -- and state the
methodology explicitly:

> *"Models are tested in 'Instruct' mode because this generally works better with the testing
> harness."* ... *"Testing via 'thinking' mode also shows the metrics (and changes) but not the
> true extent."*

Instruct mode emits no reasoning block. So the published numbers cannot speak to thinking length at
all, and the thinking claim -- *"Strong reduction in overthinking / thinking tokens (1/2 to 1/10
'normal' Qwen size)"*, *"median reduction: 2/3 roughly"* -- appears as unquantified prose on both
cards with no measurement behind it.

The accuracy tables also do not isolate TURBO: the comparison row is `Qwen3.8-27B-Instruct mxfp8`
(arc/c 0.591) against `Stage 1b (735) mxfp8` (arc/c 0.735) -- merge versus stock, the same
confound our runs have. The card names a non-TURBO baseline
(`Qwen3.8-27B-Cold-Fable-Fusion-GAIN-V1.1-732`) but does not benchmark thinking against it.

This does not make the claim false -- our 5-prompt K=1 runs do not make it false either. It means
**there is no published measurement on either side except ours**, and ours says the opposite in
both regimes tested. Stated as a limit on him, not a win for us.


---

**Follow-up, same day:** [RESULT_TURBO_TOOL_REGIME.md](RESULT_TURBO_TOOL_REGIME.md)
re-runs both arms with a `tools` array present. Thinking collapses to 695 (turbo) vs 552 (control)
characters -- a **25.2x** drop for TURBO and **12.6x** for stock. The one-sentence-then-tool-call
behaviour users praise is a property of the tool regime across the whole model family, not of this
merge. TURBO is still 1.26x more verbose there, but completion tokens land within 8%.
