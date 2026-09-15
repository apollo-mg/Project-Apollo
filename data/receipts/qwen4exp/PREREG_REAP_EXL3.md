# Prereg — experts vs precision at matched VRAM: REAP-384 @ 4.00bpw against stock @ 3.05bpw

**Written 2026-09-15, before anything is downloaded and before any arm runs.**

## The question

Expert pruning (REAP) releases are usually compared against their own unpruned parent at *different*
sizes, which can only flatter the pruned build. The honest comparison is **at matched VRAM**: for a fixed
byte budget, is it better to keep every expert at low precision, or drop a third of them and spend the
savings on bitrate?

Two builds make that comparison almost exactly, without either being chosen for it:

| build | experts | bpw | total | n-gram/PLE table | **GPU-resident weights** |
|---|---:|---:|---:|---:|---:|
| `MidnightPhreaker/…REAP-384-exl3-4.00bpw-REAP-MTP-Q4` | 384 | 4.00 | 73.1 GiB | 24.44 GiB | **48.7 GiB** |
| `turboderp …Flash-Next-exl3-3.05bpw_h5_ng5` (held on `.194`) | 512 | 3.05 | 80.0 GiB | 30.40 GiB | **49.6 GiB** |

The PLE / n-gram table is `LLM_TENSOR_LAYER_INPUT` and structurally CPU-resident
(`RESULT_FLASHNEXT_RESIDENCY.md`), so it is excluded from the matched quantity. **GPU-resident weights
differ by 1.8%.**

## Mark's prior, stated as the prediction so it is the thing on trial

> *"They almost always prove a smaller model beats a REAP of ~ size, but I'm always happy to be proven
> wrong."* — 2026-09-15

| id | prediction | falsified if |
|---|---|---|
| **P-R1** | **the unpruned build wins at matched VRAM**: stock 3.05bpw has lower mean KLD than REAP-384 4.00bpw against the same f16 reference | REAP-384's mean KLD is lower by more than the combined error |
| **P-R2** | if REAP wins, it is not by much: \|ΔKLD\| < 20% either way | either build wins by > 20% |
| **P-R3** | **MTP survives pruning**: REAP-384's speculative acceptance is within 0.05 of the stock build's on the same prompts | acceptance drops more than 0.05 |

**P-R3 is the novel one.** REAP prunes experts; MTP heads route into experts. This build re-converted the
MTP heads independently (`-mb 4 -hq`) and its card states plainly: *"No inference, speculative acceptance,
KL or perplexity benchmark was run for this Q4 derivative."* **Nobody has measured whether speculative
acceptance survives expert pruning.** Salience R6 gave 0.698 on this harness two days ago, so the
instrument exists and has a recent reference point.

## The confound, stated before the data

**The two builds were quantized by different people.** MidnightPhreaker's card says the non-MTP files are
**byte-identical to a parent conversion** by a third party; the stock build is turboderp's. So a loss by
REAP-384 could be *its quantizer* rather than *pruning*.

**This cannot be resolved with these two artifacts.** Options, in order of cost:
1. Report the result as **"this REAP build vs this stock build"**, never as "REAP vs unpruned". Cheap and
   honest, and it is what this prereg commits to.
2. Convert `sh0wie/…REAP-288-bf16` and stock Flash-Next bf16 with one recipe on our own hardware, which
   isolates pruning properly. Expensive, and out of scope here.

**The headline may not say "pruning costs X".** It may only say "this 73 GiB build beats/loses to this
80 GiB build", which is still the first number published for either.

## Amendment 1 — 2026-09-15, before any download. **The prior already exists, and it is sharper than P-R1.**

This prereg was written without retrieving `knowledge-vs-reasoning/RESULT_differential_knowledge_vs_code.md`
(2026-08-07), which measured exactly this question on a different REAP model and **already has a mechanism**:

> *"REAP scores experts by router-gate × activation-norm over that set, so an expert that never fires on
> `evol-codealpaca` reads as low-saliency and is removed. Factual recall does not fire on code."*

Result, `GLM-4.7-Flash-Q6_K` (29.94 B) vs `GLM-4.7-Flash-REAP-23B-A3B-Q6_K` (23.00 B), paired design:

| axis | base | pruned | delta |
|---|---:|---:|---:|
| **code** — HumanEval+ pass@1, 164 problems | 82.32% | **83.54%** | **+1.22 pp** |
| **knowledge** | — | — | **−56 pp** (P-R1 falsified by the premise, not the margin) |

Damage was **broad and uniform** (+33–48 pp across T1–T4), not tail-selective.

**Consequences for this stage:**

1. **P-R1 as written is measuring the wrong axis.** A single mean KLD against a general corpus mixes a
   preserved axis with a destroyed one and reports their average, which is a number about nothing.
   **P-R1 is replaced by P-R1a/P-R1b below.**
2. **sh0wie's REAP-288 card reports HumanEval 93.9 → 91.5** — a *code* benchmark, the axis this fleet's
   own data says is preserved. Their 2.4-point drop is inside both the noise and the prediction. **They
   measured the axis that cannot lose**, and their calibration corpus (~686K tokens of agentic-coding
   traffic) has the same code bias as Cerebras's.

| id | prediction | falsified if |
|---|---|---|
| **P-R1a** | **code axis: REAP-384 ties or beats stock at matched VRAM** — consistent with +1.22 pp at 25% pruning, and 384/512 is a *lighter* 25% prune | REAP loses by more than the paired margin |
| **P-R1b** | **knowledge axis: REAP-384 is materially worse**, and the gap is far larger than the code gap | knowledge gap ≤ code gap |
| **P-R1c** | **the split is the finding**: \|knowledge delta\| ≥ 5× \|code delta\| | ratio < 5× |

**Mark's stated prior is refined, not discarded.** *"A smaller model beats a REAP of ~ size"* holds on
knowledge and **is contradicted on code by this fleet's own measurement**. The honest version is:
**pruning buys code-per-byte and sells knowledge-per-byte**, and which one wins depends entirely on
which axis you benchmark — which is why almost every published REAP card reports code.

**Recorded as a process failure too.** This prereg proposed an experiment whose directly relevant prior
result was five weeks old and sitting in `data/receipts/`. Nothing connected them; the retrieval was
available and the *connection* was not made. That is the exact failure `tools/DESIGN_INTENT_CONTINUITY.md`
describes — not a retrieval problem, a verification-and-linkage problem — and it is the clearest instance
of it recorded so far, because the prior was not merely relevant but decisive.

## Method

Same harness as the EXL3 campaign: `llama-perplexity`-derived KLD against a stored f16 reference on the
identical token set, `.194`, 4× P100 sm_60, `-sm layer` (EXL3 multi-device tensor split is rejected),
KV `f16` verified from `-lv 4`, page cache dropped per arm. Engine: **ExLlamaV3 ≥ v1.4.8**, which the REAP
card names as required for sharded n-gram tables — **verify the installed version before the run; if it is
older the arm does not run, it aborts.**

**Noise floor applies.** `RESULT_FLASHNEXT_BREAK.md` measured 2–4% run-to-run variance in decode at fixed
everything. KLD is a different statistic and its own variance is unmeasured here, so **P-R1 is scored on
the KLD error bars the harness already reports, and any difference under 20% is reported as "within
instrument" rather than a win** (P-R2 exists to force that).

## Cost and preconditions

- **73.1 GiB download.** `.194` has 160 GB free after yesterday's cleanup; the mirror running today does
  not touch it.
- Record the sha256 of every downloaded file **at fetch time**. Today's audit found three cited builds
  permanently unrecoverable, one of them re-quantized in place under an identical filename
  (`RESULT_MODEL_AVAILABILITY_AUDIT.md`). **A REAP build from a single uploader with 320 downloads is
  exactly the profile that vanishes.**
- Do not start while the model mirror is writing to the same volumes.

## Not predicted

Throughput. Fewer experts should decode faster, but 5b showed this instrument cannot resolve small
throughput differences without repeats, and no repeat budget is allocated here.
