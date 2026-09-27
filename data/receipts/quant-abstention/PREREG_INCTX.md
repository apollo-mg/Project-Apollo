# Pre-registration -- quant-abstention INCTX: is a quant's "I don't know" shifted where its generation actually decides?

**Drafted 2026-09-27, before any in-context pass is run.** A 24-item smoke test (Q8_0 reading its own and AD IQ2_XS's
prose, to test the probe) ran first; its outputs were deleted. Runner `run_inctx.py`, launcher `run_inctx_lanes.py`.
The analysis (`analyze_inctx.py`) implements the rules below. It is committed before any in-context output is opened.

**Prior art checked:** `ledger_precheck.py "logit bias recalibration abstention threshold per-file offset quant"`
(this session) plus the quant-abstention receipts. Found:
- MAIN (INDEX L503: slot labels);
- CALIB (the offset fix, slot only);
- the AD ladder (L148: in *generation*, AD IQ2_XS abstained 24/24 on its CAL items, which never squared with main's
  slot label "confident" for the same file).

**What this adds:** the soft P(UNKNOWN) at the point in a real generation where the answer is chosen, the ranking at
that point, and a split of any shift into what the quant *writes* and how it *reads*.

## Why (found in stored data, 2026-09-27, before this prereg)

Main's forced slot (prompt + "Exact Answer:", nothing written) and main's own generations disagree for the files
labelled confident. Same items, invented arm, per-item paired, 95 %:

| file | forced-slot greedy confabulation shift | generation shift | forced - generation |
|---|---:|---:|---|
| AD IQ2_XS | +0.162 | -0.020 | +0.182 [+0.082, +0.282] |
| APEX I-Nano | +0.093 | -0.031 | +0.124 [+0.010, +0.237] |
| EXL3 3.5 | +0.081 | -0.071 | +0.152 [+0.060, +0.243] |
| AD IQ3_XXS (timid) | -0.146 | -0.135 | -0.010 [-0.114, +0.094] |
| Bonsai PQ2_0 | +0.086 | +0.151 | -0.065 [-0.169, +0.040] |

The pilot showed the same pattern (AD IQ2_XS: forced +0.21 soft, generation +0.03).

In a real generation, the model writes about one sentence before "Exact Answer:". This asks what that sentence does to
the readout.

## Design

- **Instrument:** identical to main: .194, buun 0b2789f23 sm_60, the main flags (`serve_main.sh`), f16 KV verified
  and no MTP/draft line per server, the ceiling's render tail and variant ids required, raw logits
  (`post_sampling_probs: false`), `cache_prompt: false`, one discarded warm-up per server.
- **Read:** reader R reads writer W's prose, meaning R's own render of the CAL prompt (thinking off) plus W's stored
  main-campaign content up to and including the colon of the last "Exact Answer:". n_predict 1, n_probs 50.
  P_abs = the sum of the three UNKNOWN variants.
  - Usable items: every item whose stored generation contains "Exact Answer:", i.e. all graded items. TRUNCATED and
    NO-ANSWER items have none, and that is the only filter.
- **Passes:**
  - own prose, all 23 files (Q8_0 and 22 arms), E, H and U items;
  - swaps, for 7 key files (the five labelled confident: AD IQ2_XS, AP IQ3_XXS, APEX I-Nano, EXL3 3.0, EXL3 3.5;
    plus AD IQ3_XXS and Bonsai PTQ1_0), U items only: the file reads Q8_0's prose, and Q8_0 reads the file's.
- **Probe (gate):** on own-prose passes, the greedy token must be the start of what the stored generation wrote after
  the cut. Items that fail are excluded from that file's metrics and counted.
  - A file under 95 % pass is reported but flagged.
  - Q8_0 under 99 % stops the analysis (instrument).
  - Smoke: 24/24.

## Metrics (own prose, arm vs Q8_0, over items usable and probe-passing in both)

- timidity_ctx = mean P_abs on H; confabulation_ctx = mean (1 - P_abs) on U;
- discrimination_ctx = within-template AUROC of P_abs, U vs E+H, averaged over the 4 templates.

Main's statistics are used unchanged: paired t-intervals and a 200,000-resample stratified bootstrap. The level is
1 - 0.05/60 for the 20 PTQ arms and 95 % for Bonsai. Direction labels use main's `direction()` rule.

## Confirmatory claims

- **H-ctx-rank: the ranking survives at the decision point.** Supported if >= 18 of the 20 PTQ arms have |d
  discrimination_ctx| <= 0.03 with an interval that includes 0 (main's forced slot: 19 of 20). Not supported if
  <= 14; partial otherwise.
- **H-ctx-confident: the confident shift is a forced-slot effect.** For each of the five confident-labelled files, U
  items usable in both:
  - per item, (P_C - P_arm) at the forced slot minus (P_C - P_arm) in context (soft);
  - 95 % paired t-interval.

  A file "shrinks" if the lower bound is > 0. Supported if >= 4 of 5 shrink, not supported if <= 1, partial
  otherwise.

## Secondary (registered, descriptive, 95 %)

- **Labels in context** for all 22 arms, next to their main labels. Kappa is not reported: the in-context greedy
  decision *is* the generation's decision (that is the probe).
- **Reading vs writing** for the 7 key files (U items, confabulation direction, P_C - P_arm form):

  | component | definition | meaning |
  |---|---|---|
  | total | own_arm - own_C | the full in-context shift |
  | reading on Q8_0's prose | arm(C prose) - C(C prose) | how differently the arm reads the same sentence |
  | writing | C(arm prose) - C(C prose) | what the arm's sentence does to Q8_0's reading |
  | reading on the arm's prose | total - writing | |

- **Forced vs in context vs generation**, per arm, side by side (forced and generation from main).

## Not established by design

- **One sample of prose.** Each file's prose is its greedy generation from main, a single sample.
- **Swaps cover U items and 7 files only.** That is the time budget: about 2.5 s per read on this instrument.
- **One model, thinking off, one prompt,** as in main.
- **Stage 2 of CALIB is re-scoped by this run.** Its live `logit_bias` generations were not run, because main's
  generations already refuse at Q8_0's rate on the confident files (`RESULT_CALIB.md`, note).
