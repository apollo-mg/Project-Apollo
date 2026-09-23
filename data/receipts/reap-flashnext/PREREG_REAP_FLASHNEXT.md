# Pre-registration — REAP on Qwen3.8-Flash-Next: what pruning costs, and whether quantizing is the better way to shrink

**2026-09-23, written before any inference on any arm.** `.194`, 4x Tesla P100 (sm_60), buun
`08826ad6e` (`build_sm60_0920`). Runner and batteries execute **on .194 itself**. They do not touch
the desktop `run/benchmark.lock`, which the MTP-agentic run holds.

## Why

The REAP files for Qwen3.8-Flash-Next have ~100k downloads between them. Their card claims code and
agentic ability survive pruning. A 12-question probe in the author's own HF thread found 42 % / 25 %
fabrication for K=256 / K=320 against 0 % for unpruned UD-IQ1_M. Mark's prediction, recorded here:
**"it's probably going to suck compared to a smaller model / more quantization."**

**Prior art checked:** `ledger_precheck.py "REAP expert pruning Flash-Next versus expert spill ncmoe"`
plus a manual read of `knowledge-vs-reasoning/` -> receipts found:
- `RESULT_REAP_DOSE_RESPONSE.md` (GLM-4.7-Flash): knowledge damage is monotone and immediate; GLM
  *withdraws* (refusal 97 % at 50 % pruned).
- `RESULT_FIXED_BYTE.md` (GLM, ~13.2 GB fixed): pruning is the worst way to spend bytes. Unpruned
  3-bit beat half-pruned 6-bit by 37.8 pp. **Knowledge only.**
- `RESULT_QWEN_CALIBRATION_CONTRAST.md` (Qwen3.6-35B REAP20): -31.4 pp knowledge even with general
  calibration. Qwen *fabricates* rather than withdraws (refusal 11.9 %).
- `RESULT_differential_knowledge_vs_code.md` (GLM REAP): code +1.2 pp (HumanEval+), knowledge
  -36.8 pp.

**What this adds:**
1. A fine-grained 512-expert, top-10 Qwen MoE at 117B.
2. A **byte-verified exact-parent pair** (`NOTE_REAP320_Q2_PARENT_VERIFIED.md`).
3. **Code at a fixed byte budget.** FIXED_BYTE measured knowledge only, so whether the answer splits
   by domain ("prune for code, quantize for knowledge") is unmeasured.
4. A practitioner comparison against a dense 27B.

## Arms (all headers verified: `qwen4exp`, `expert_used_count 10`, identical 9,993-byte chat template)

| id | file | experts | size | role |
|---|---|---:|---:|---|
| `FULLQ2` | Unsloth UD-Q2_K_XL | 512 | 73.5 GiB | exact parent of `R320Q2` |
| `R320Q2` | AnonimousA REAP-320 `Q2/` | 320 | 57.3 GiB | pruned, same bits as `FULLQ2` |
| `R320Q3` | AnonimousA REAP-320 main (UD-Q3_K_XL lineage) | 320 | 64.2 GiB | **prune** arm at the matched budget |
| `IQ1S` | Unsloth UD-IQ1_S | 512 | 67.6 GiB | **quantize** arm at the matched budget (+5.3 % over `R320Q3`) |
| `IQ4XS` | Unsloth UD-IQ4_XS | 512 | 87.2 GiB | high-fidelity reference |
| `D27Q6` | Qwen3.8-27B Q6_K (dense) | — | 21.3 GiB | **practitioner** comparison: not controlled (other architecture, a third of the bytes) |

`R320Q3` and `IQ1S` are downloading at registration time. They are recorded here before they exist
locally. Their sha256 values will be checked against the upstream LFS oids before use.

**Comparisons, labelled by what they are:**
- **C1, exact parent (single variable):** `R320Q2` vs `FULLQ2`. Placement is matched: all arms load
  fully on GPU with `-ngl 99 -sm layer` (load probe, 2026-09-23).
- **C2, matched budget (an allocation comparison, not single-variable):** `R320Q3` vs `IQ1S`. Expert
  count and bits both differ; that trade is the point. Calibration is not a confound here, since
  only one arm is pruned.
- **C3, practitioner:** `D27Q6` against each Flash-Next arm, descriptive only.

## Fixed setup

- `llama-server -ngl 99 -sm layer -c 8192 -fa on -np 1 --no-cache-prompt --jinja -v`,
  `GGML_CUDA_ALLREDUCE=internal`. The prompt cache is off because prefix reuse segfaults on this model
  (`qwen4exp/RESULT_META_BACKEND_SEGFAULT.md`), and every probe here is single-turn anyway.
- **Thinking OFF, temp 0, one sample** for both batteries. This differs from the GLM HumanEval+ run
  (thinking on), and is chosen because Flash-Next decode on P100 makes thinking-on HumanEval+ across
  six arms infeasible. Knowledge recall must be thinking-off in any case (`ikp_run.py --no-think`).
- The server restarts per arm and one warmup generation is discarded. GPU clocks and power are
  recorded per arm.

## Batteries

- **Knowledge:** `ikp/ikp_run.py` + `ikp_score.py` **unmodified**, `--exclude-source researcher`,
  T1-T4 (714 probes), `--max-tokens 64`, `--no-think`.
- **Code:** `humaneval-plus/hep_eval.py`, 164 HumanEval+ problems (`humanevalplus.jsonl`, 11,317,638
  B), `HEP_TEMP=0`, `HEP_K=1`, thinking off via the template kwarg, `HEP_MAXTOK=4096`, and
  `preflight()` must be green.

## Metrics

- IKP: raw accuracy, refusal, committed accuracy and **fabrication** (wrong among committed), per tier
  and overall.
- **Termination is its own bucket.** Empty content, `finish_reason: length`, or reasoning text in
  `content` are counted separately and never as refusals. REAP-256 had a reported stall, and a stall
  must not read as withdrawal.
- HumanEval+: pass@1, plus the PASS / WRONG / TRUNCATED / NO_ANSWER buckets.
- Paired exact McNemar per comparison, on per-probe and per-problem outcomes (deterministic at temp
  0, np 1).

## Gates

- **G0, base validity:** `FULLQ2` T1 committed accuracy ≥ 85 %. If it fails, Q2 is already broken, C1
  measures pruning on a damaged base, and `IQ4XS` becomes the C1 reference **with the bits confound
  stated**.
- **G1:** each arm's `/props` model path, `n_expert` from the load log, and all layers on GPU (buffer
  lines, `-v`) asserted before its first probe.
- **G2:** thinking actually off. `reasoning_content` must be empty on the first 5 probes of each arm.
- **G3:** `hep_eval` preflight green; the `R320Q3` and `IQ1S` hashes match upstream.

## Predictions (confidence)

| # | claim | test | conf |
|---|---|---|---:|
| H1 | pruning costs knowledge (C1) | `R320Q2` raw IKP accuracy below `FULLQ2` by ≥ 10 pp, McNemar p < .05 | 0.85 |
| H2 | pruning spares code (C1) | `R320Q2` HumanEval+ within ±5 pp of `FULLQ2` | 0.55 |
| H3 | **Mark: quantizing beats pruning on knowledge at matched bytes** (C2) | `IQ1S` raw IKP accuracy above `R320Q3`, p < .05 | 0.80 |
| H4 | …but not on code (C2) | `R320Q3` HumanEval+ ≥ `IQ1S` | 0.50 |
| H5 | pruned Qwen fabricates rather than withdraws | refusal rate < 25 % on both REAP arms | 0.70 |

**Unfavourable outcomes named now:**
- H2 false: REAP's own claim fails on this model.
- H3 false: Mark's prediction fails and FIXED_BYTE does not generalize to Qwen fine-grained MoE.
- H3 true and H4 true: the domain split exists, and the practitioner advice becomes "prune for code,
  quantize for knowledge".

## Not established whatever the outcome

One model family, one pruning author and calibration, thinking-off only, single-turn batteries, and
the agentic claim is **not** tested here. Argus (agentic) is a phase 2, after the MTP-agentic run
frees the desktop harness.
