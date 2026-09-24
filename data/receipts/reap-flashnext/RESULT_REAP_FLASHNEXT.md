# REAP on Qwen3.8-Flash-Next: pruning costs 20 pp of knowledge and makes the model fabricate. At the same size, a 1-bit unpruned quant wins on knowledge and ties on code

**2026-09-23/24**, `.194`, 4x P100 (sm_60), buun `08826ad6e`, `-ngl 99 -sm layer -c 8192`, every arm fully
GPU-resident, thinking off, temp 0. Prereg: `PREREG_REAP_FLASHNEXT.md` (`ff16209`, committed before any
inference). Knowledge: `ikp_run.py`/`ikp_score.grade()` unmodified, 714 probes. Code: `hep_eval.py`, 164
HumanEval+ problems. Scorer `analyze_reapfn.py` -> `RESULT_reapfn.json`. Raw per arm in `raw/`. The 120 MB
`-v` server logs stay on .194; their gate lines are in `raw/<arm>/server_gates.txt`.

Mark's prediction, recorded in the prereg: *"it's probably going to suck compared to a smaller model / more
quantization."* **It held.**

## Results

| arm | experts | size | IKP raw | committed acc. | **fabrication** | refusal | HumanEval+ |
|---|---:|---:|---:|---:|---:|---:|---:|
| `FULLQ2` UD-Q2_K_XL | 512 | 73.5 GiB | 55.0 % | 86.2 % | 13.8 % | 0.0 % | 94.5 % |
| `R320Q2` REAP-320 (Q2) | 320 | 57.3 GiB | **35.2 %** | **50.1 %** | **49.9 %** | 1.5 % | 90.2 % |
| `R320Q3` REAP-320 (Q3) | 320 | 64.2 GiB | **35.7 %** | **51.5 %** | **48.5 %** | 0.1 % | 92.7 % |
| `IQ1S` UD-IQ1_S | 512 | 67.6 GiB | 58.5 % | 81.3 % | 18.7 % | 0.0 % | 93.9 % |
| `D27Q6` Qwen3.8-27B dense Q6_K | — | 21.3 GiB | 63.4 % | 77.6 % | 22.4 % | 2.1 % | 92.1 % |

*committed accuracy = correct / (correct + wrong); fabrication = wrong / (correct + wrong).*

## Predictions scored (exact McNemar, paired per probe / per problem)

| # | claim | result |
|---|---|---|
| H1 | pruning costs knowledge (C1, exact parent) | **HELD.** R320Q2 vs FULLQ2 raw **-19.8 pp**; 49 probes only the pruned model got right vs 191 only the parent got right, **p = 5e-21** |
| H2 | pruning spares code (C1) | **HELD** (just). HumanEval+ -4.3 pp, inside the ±5 pp band; 2 vs 9 discordant, p = 0.065 |
| H3 | **Mark: at matched bytes, quantizing beats pruning on knowledge** (C2) | **HELD, decisively.** IQ1S vs R320Q3 **+22.8 pp** raw; 192 vs 29 discordant, **p = 1e-30** |
| H4 | …but pruning wins on code (C2) | **FAILED.** IQ1S 93.9 % vs R320Q3 92.7 %; 7 vs 5, p = 0.77. **There is no domain split**: the 1-bit unpruned model ties on code and dominates on knowledge |
| H5 | pruned Qwen fabricates rather than withdraws | **HELD.** Refusals 1.5 % / 0.1 %, and **half of all committed answers are wrong** |

**Gates:**
- G0: FULLQ2 T1 committed accuracy 97.7 % ≥ 85 %.
- G1: all layers on GPU, and n_expert 512/320/512/320.
- G2: thinking off, empty reasoning.
- G3: R320Q3 and IQ1S hashes equal to upstream.
- **KV:** zero VBR degrades on every arm (see Deviations).

All passed.

## What it means

1. **Pruning is where the damage comes from, not bits.** R320Q2 vs R320Q3 (same 320 experts, Q2 vs Q3):
   knowledge identical (36 vs 40 discordant, p = 0.73), code within noise. Once experts are deleted, giving
   the survivors more bits buys nothing. The deleted experts held the knowledge.
2. **The failure is confident fabrication.** The parent is wrong on 13.8 % of the answers it commits to;
   the pruned model on ~49 %, while almost never declining. On GLM (`RESULT_REAP_DOSE_RESPONSE.md`) the
   same damage showed up as refusal. Qwen's pruned models fabricate instead, now seen on two Qwen MoEs
   (with `RESULT_QWEN_CALIBRATION_CONTRAST.md`). That is the worse failure for users, because it looks
   like an answer.
3. **"Prune for code" is not supported either.** The REAP card's case is "keeps code and agent ability,
   fits where the full model doesn't". At the same memory, Unsloth's unpruned IQ1_S keeps code just as
   well (93.9 vs 92.7 %) and knowledge far better. `FIXED_BYTE`'s GLM finding generalizes to this
   fine-grained Qwen MoE, and now covers code as well.
4. **Pruned models also slip on output format:** 7 (Q2) and 2 (Q3) HumanEval+ answers were correct-looking
   code *without a code fence*, so they could not be extracted (`NO_ANSWER`, finish = stop). The full and
   IQ1_S arms had none. It is small, but it is the same "personality differs" symptom the HF thread
   described.

**Practitioner reading (C3, descriptive, not controlled):**
- The dense 27B at a third of the bytes scores highest on *raw* knowledge, partly because it is terser and
  hits the 64-token cap less (8.7 % vs ~20 %).
- On committed accuracy it sits between full Flash-Next and the pruned builds, and it ties everything on
  code.
- For a 64 GB-class budget, **a 1-bit quant of the full model or a dense 27B both beat a REAP'd Flash-Next.**

## Deviations from the prereg (all recorded before scoring unless noted)

- **KV cache:** the runner passed no `-ctk`, so buun's default dynamic VBR was active (my error; the rule
  is to pass KV flags explicitly). VBR enters at f16 and **degraded zero times on every arm**, so every arm
  ran an f16 KV cache. A gate enforcing this was added before arms 3-5 ran.
- **`IQ4XS` dropped:** 87 GiB does not fit fully on 4x16 GB (`cudaMalloc` OOM on device 0). The prereg
  used it only if G0 failed, and G0 passed.
- **The 64-token cap truncated ~9-23 % of answers per arm** (Flash-Next appends an explanation). The
  unmodified scorer books those as NO_ANSWER. A **post-hoc** re-grade of truncated rows on their content
  changes **no CORRECT count and no test result**: the truncated answers exceed the scorer's 25-word
  limit and become AMBIGUOUS, not correct. Raw accuracy across models with different verbosity (C3) is
  affected by this, which is why the committed-accuracy column is also reported.

## What this adds to prior art

The first REAP measurement on a **512-expert fine-grained Qwen MoE**, with a **byte-verified exact-parent
pair** (`NOTE_REAP320_Q2_PARENT_VERIFIED.md`), and the first **code** measurement at a **fixed byte
budget**. It replicates FIXED_BYTE (GLM) and the Qwen REAP20 fabrication pattern, and falsifies the one
open hope for REAP at a fixed budget: that it would at least win on code.

## Not established

- One pruning author and calibration (multi-domain, activation-count salience). True router-weighted
  REAP might differ.
- Thinking off only, single-turn, one decoding setting.
- **Agentic ability is not tested here.** That is REAP's other claim, and argus phase 2 would cover it.
- HumanEval+ is near ceiling for every arm, so small code differences are below this instrument's
  resolution.
