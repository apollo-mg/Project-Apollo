# Pre-registration: does a KL-optimised expert pruner (RCO, ISTA's "Coder") avoid REAP's knowledge loss and fabrication?

**Registered 2026-10-01, before any row.** Mark: "Let's give the coder model a try." The model:
`ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF` @ `5348543e`, IQ1_M.
- **The pruning:** 256 of 512 experts kept per layer, selected by RCO to minimise KL divergence to the full model on a
  code + agentic + vision calibration mix.
- **Size:** 3.5 bpw on what remains; 29.6 GB resident (shard 1) plus the 28.8 GB n-gram table.
- **The card's claim:** 91.3 % of SWE-bench Verified and 98.7 % of LiveCodeBench v6 retained.

**Prior art checked:** `ledger_precheck.py "expert pruning REAP knowledge fabrication"` -> receipts found:
- `reap-flashnext/RESULT_REAP_FLASHNEXT.md` (09-23/24), REAP-320 on Flash-Next:
  - **-19.8 pp IKP raw vs its exact parent** (p = 5e-21);
  - **fabrication 49.9 % vs 13.8 %**, refusals ~0;
  - HumanEval+ -4.3 pp;
  - at matched bytes, an unpruned 1-bit quant beat the pruned 3-bit by +22.8 pp on knowledge and tied on code;
- `knowledge-vs-reasoning/` (GLM REAP, 25 % pruned): code untouched, T1 factual recall -36.8 pp.

**What this adds:**
- A different pruner. REAP ranks experts by saliency; RCO optimises the full model's KL jointly with per-layer budgets.
- A deeper cut: 50 % of experts removed against REAP-320's 37.5 %.
- A matched parent from the same ISTA pipeline: the unpruned GSQ-RCO IQ3_XXS (FNGB, sha256 `219ea929…6d15` /
  `316b46f3…e113`), whose M1 results are already stored (`viability/RESULT_SWIFT_FLASHNEXT.md`).

## Arms

| arm | file | experts | GPU-resident |
|---|---|---:|---:|
| **CODER** | ISTA GSQ-RCO Coder IQ1_M, shard 1 sha256 `e11083ba…7fad` | 256 | 29.6 GB |
| **FNGB** | ISTA GSQ-RCO IQ3_XXS (unpruned parent) | 512 | 47.0 GB |

**Shard 2 is the same file in both:** the Coder's n-gram table has the base's sha256 (`316b46f3…`) and is symlinked.

**Not a pure pruning ablation:**
- ISTA re-spent the saved bytes. 866 of the Coder's 1,079 non-expert tensors match the base allocation; the rest are
  mostly *higher* precision (e.g. `attn_qkv` q6_K vs iq4_xs, `output` q6_K vs q5_K).
- The kept experts use a different type mix.

So this compares the shipped artifacts. If pruning still costs knowledge, it does so despite better dense weights.

## Instrument

- **The REAP study's instruments, unchanged since 08-06:**
  - IKP, `ikp_run.py --tiers T1,T2,T3,T4 --max-tokens 64 --no-think --exclude-source researcher`, 714 probes
    (`ikp_probes.json`, sha256 `fe8c84af…`);
  - HumanEval+, `hep_eval.py` (sha256 `65260e72…`), 164 problems, temp 0, k=1, thinking off, 4096 max tokens.
- **Scoring:** `ikp_score.grade()` unmodified; committed = C/(C+W); fabrication = W/(C+W); exact McNemar per probe
  and per problem. `analyze_reapfn.py`'s scoring functions are copied verbatim (that file runs on import).
- **CODER only, M1** (`quant-abstention/run_main.py`, 240 items, thinking off, temp 0, Qwen3.8 UNKNOWN ids), against
  FNGB's stored M1 rows.
- **Host and build:** .194, 4x P100 at 150 W / 1063 MHz (read back), buun `0b2789f23` (the build FNGB's M1 used; its
  g64 Q2_0 load was verified on 09-29). `-ngl 99 -sm layer -ts 1,1,1,0.6 -c 8192 -fa on -np 1 --no-cache-prompt
  --jinja`, f16 KV passed explicitly, chat-template kwargs `{"reasoning_effort":"medium","enable_thinking":false}`
  as in REAP.
- **Difference from REAP:** buun `08826ad6e` there, and buun's default VBR with a zero-degrade gate. Cross-study
  numbers are context, not a test.
- **Gates per arm:**
  - G1: `/props` names the file; `n_expert` matches (256 / 512); 49/49 layers on GPU;
  - G2: thinking off (empty reasoning, non-empty content);
  - G3: the Coder's shard 1 sha256 matches the manifest; `type q2_0` loads with no Bonsai g128 remap.
- **Order:** CODER (IKP, HEP, M1), then FNGB (IKP, HEP). Each arm runs on a fresh verified server.

## Predictions (`analyze_coder.py`, committed with this file; self-tested on REAP's stored arms)

| # | claim | rule | confidence |
|---|---|---|---|
| C1 | **RCO pruning still costs knowledge** | IKP raw CODER - FNGB <= -10 pp, McNemar p < 0.01 | 0.7 |
| C2 | **...and the pruned model fabricates more** | fabrication CODER >= FNGB + 15 pp | 0.6 |
| C3 | **RCO damages knowledge less than REAP did**, despite cutting deeper | IKP raw CODER - FNGB > -19.8 pp (REAP-320's drop vs its parent) | 0.5 |
| C4 | **Code is spared** (the card's claim) | HumanEval+ CODER within 5 pp of FNGB | 0.6 |

**Reported without a prediction:**
- per-tier IKP (T1 = common facts);
- refusal and no-answer rates;
- M1 easy/hard/invented for CODER against FNGB's stored rows (refusal of invented items is the M1 analogue of C2);
- REAP's table as cross-study context.

**Scope:** one pruned model, one parent, thinking off. Code is HumanEval+ only; SWE-bench-style agentic work, the
card's headline, is not measured.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
