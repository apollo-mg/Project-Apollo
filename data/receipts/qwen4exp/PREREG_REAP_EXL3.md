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
