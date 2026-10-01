# Result -- KL-optimised expert pruning (ISTA's GSQ-RCO Coder) keeps code and loses knowledge worse than REAP did: -30.4 pp against its own unpruned parent, fabrication 14 % -> 52 %, zero refusals; HumanEval+ unchanged (93.3 vs 93.9 %)

**2026-10-01.** Pre-registration `PREREG_CODER_PRUNE.md` (`e58d7c3`), no deviations. Runner `run_coder.sh` +
`coder_eval.sh`, analysis `analyze_coder.py` (self-tested on REAP's stored arms; it reproduced their -19.9 pp and 49.9 %
fabrication), output `RESULT_coder.json`.

- **Raw:** `raw/{CODER,FNGB}/` (`ikp.jsonl`, 714 rows; HumanEval+ results and traces; server logs, paths redacted) and
  `../quant-abstention/raw/main_CODER.jsonl` (M1, 240 rows).
- **Host and build:** .194, 4x P100 at 150 W / 1063 MHz, buun `0b2789f23`, `-ngl 99 -sm layer -ts 1,1,1,0.6 -c 8192
  -fa on -np 1`, f16 KV, thinking off.
- **Gates (both arms):** `n_expert` 256 / 512 from the server's own log, 49/49 on GPU, Q2_0 loaded as g64 (9 / 38
  tensors), no Bonsai remap, thinking off (empty reasoning; 0/164 HumanEval+ samples reasoned). The Coder's shard 1
  matched the manifest sha256; shard 2 is byte-identical to the parent's.

## Registered verdicts

| # | claim | result |
|---|---|---|
| C1 | RCO pruning still costs knowledge (<= -10 pp, p < 0.01) | **holds.** **-30.4 pp** (63.3 -> 32.9 %); 242 probes only the parent got right vs 25 only the Coder, **p = 9e-46** |
| C2 | the pruned model fabricates more (>= +15 pp) | **holds.** fabrication **14.2 % -> 52.3 %** |
| C3 | RCO damages knowledge less than REAP did (> -19.8 pp) | **does not hold.** -30.4 pp, worse than REAP-320's -19.8 |
| C4 | code is spared (within 5 pp) | **holds.** HumanEval+ 93.3 vs 93.9 % (3 vs 4 discordant, p = 1.0) |

## Knowledge (IKP, 714 probes, thinking off)

| arm | experts | raw | committed acc. | **fabrication** | refusal | T1 | T2 | T3 | T4 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **FNGB**: unpruned GSQ-RCO IQ3_XXS | 512 | **63.3 %** | 85.8 % | 14.2 % | 0.0 % | 72.0 | 73.0 | 57.0 | 45.6 |
| **CODER**: RCO-pruned | 256 | **32.9 %** | 47.7 % | **52.3 %** | 0.0 % | 54.5 | 40.0 | 19.4 | 9.4 |

**What is lost is long-tail entity facts.**

| | parent -> Coder | fabrication |
|---|---|---|
| T1 (well known) | 72.0 -> 54.5 (-17.5) | 1 % -> 20 % |
| T2 | 73.0 -> 40.0 (-33.0) | 3 % -> 36 % |
| T3 | 57.0 -> 19.4 (-37.6) | 18 % -> 71 % |
| T4 (obscure) | 45.6 -> 9.4 (-36.2) | 41 % -> **89 %** |
| Wikidata entity facts (n=216) | 63.9 -> 19.9 (**-44.0**) | 31 % -> 79 % |
| LLM-written general probes (n=401) | 60.8 -> 33.4 (-27.4) | 4 % -> 40 % |

- **Domains with >= 20 probes, ordered by loss:**
  - universities 85.7 -> 4.8;
  - journal founding years 85.2 -> 22.2;
  - journals 75.9 -> 17.2;
  - history 90.9 -> 32.7;
  - founding years 56.7 -> 6.7;
  - culture -24;
  - science -11;
  - geography -7;
  - places -5;
  - "general" -1.
- **No refusals at all.** The model does not become unsure about what it lost; it answers it.

## M1 (240 items, thinking off) against the parent's stored rows (09-29, same build and corpus)

| arm | regional capitals ("easy") | hard: correct | hard: answered wrong | invented: refused |
|---|---:|---:|---:|---:|
| FNGB | 0.90 | 0.83 | 0.15 | 0.74 |
| **CODER** | **0.28** | **0.35** | **0.56** | 0.61 |

The "easy" collapse was checked row by row and is genuine. The answers are confident and well formatted:
- "The capital of the state of Maranhão is **Recife**" (it is São Luís);
- "The capital of the Altai Republic is **Omsk**" (it is Gorno-Altaysk);
- North Gyeongsang Province placed "(North Korea)".

## What it means

- **The KL-optimised pruner did not avoid REAP's failure; it reproduced it at a deeper cut.**
  - REAP-320 (37.5 % of experts removed, UD-Q2): -19.8 pp, fabrication 13.8 -> 49.9 %.
  - RCO Coder (50 % removed, vision in calibration, dense weights *upgraded*): -30.4 pp, fabrication 14.2 -> 52.3 %.
  - In both, code is untouched and refusals stay at zero.
- **The card's claims are true and incomplete.** HumanEval+ is unchanged, consistent with its SWE-bench and
  LiveCodeBench retention. What the calibration mix does not exercise (long-tail facts about specific entities) is
  removed. The model is not told it is missing, and fabricates in its place.
- **The failure is invisible to the usual checks:** capability benchmarks pass by construction, and no refusal or
  hedging signals the loss.
- **A pruned model's card should report calibration against its parent** (IKP / M1 / CAL style), not only capability
  scores. Mark's verdict: "Pruning is dangerous IMO ... it's far too ambiguous how much you can actually trust these
  models in practice."
- **Cross-study side note:** the unpruned GSQ-RCO IQ3_XXS scores 63.3 % raw on IKP, against the unsloth UD-Q2_K_XL's
  55.0 % in the REAP study (a different buun build and KV setup). That matches Tuesday's slight GSQ edge on M1.

## Not established

- One pruned model, one calibration mix, thinking off. Agentic coding (SWE-bench), the card's headline, was not run.
- Not a pure pruning ablation: ISTA re-spent the saved bytes on higher-precision dense weights. The loss happened
  despite that.
- Whether the lost facts live in the removed experts was not shown directly. That needs expert-routing logs on the full
  model (`llama-eval-callback`), compared with RCO's kept set.
