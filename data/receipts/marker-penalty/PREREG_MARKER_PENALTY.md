# Pre-registration -- does a logit penalty on hesitation markers shorten Qwen3.8-27B's thinking without costing calibration, and equally at Q6_K and IQ3_XXS?

**2026-09-25, before any generation.** The follow-up named in `quant-hesitation/RESULT_HESITATION_KLD.md`.

**Source (quoted, re-read 2026-09-25):** Lotfi et al. "introduce a logit penalty on 50 curated overthinking
markers": "At each decoding step t, we modify the logits z_t(v) for each token v in S by subtracting a fixed penalty
lambda > 0". It "consistently reduces CoT length by 12 to 23% on average across 5 models". lambda is swept "from 0.5
to 4.0", with the best reported per configuration. The page lists "Wait", "But", "Alternatively", "perhaps", "maybe",
"however", "reconsider", "backtrack", "wrong"; the full list of 50 is in the paper.

**Prior art checked:** `ledger_precheck.py "logit bias penalty hesitation markers reasoning length overthinking"` ->
- no marker-penalty test exists;
- related: `viability/RESULT_OVERTHINK_INJECTION_Q6K.md` (09-12). At Q6_K `xhigh`, a thinking cap cut deliberation
  on unanswerable items by 88.7 % with no answerable cost; an injected nudge did nothing.
- `quant-hesitation/RESULT_HESITATION_KLD.md` (09-24): quantization does not single out the marker positions (at
  matched entropy they take ~30 % less KLD).

**What this adds:** the source's intervention on this model family, on the calibration instrument that already has a
Q6_K baseline. It also tests the KLD result's prediction that the penalty's effect does not depend on bit depth.

## Instrument (same as 09-12 except the model and build)

- `.194` split into two 2-GPU testers (device count 2 for every arm), buun `08826ad6e` `build_sm60_0920`,
  `-ngl 99 -c 16384 -np 1 -fa on --kv-unified -ctk f16 -ctv f16 -sm tensor --jinja`, `GGML_CUDA_ALLREDUCE=internal`.
  - GPUs 0,1: **`Qwen3.8-27B-Q6_K`** (22,884,408,288 B).
  - GPUs 2,3: **`Qwen3.8-27B-UD-IQ3_XXS`** (11,913,559,104 B: the earlier Unsloth upload, the same file as the KLD
    receipt).
- `viability/run_fixture_structfix.py --tier cal --sampling card --effort xhigh`, `n_predict` 6144 (the tier's).
  Items CAL-A1..A8 (answerable) and CAL-U1..U8 (unanswerable); 3 reps, seeds 1001-1003. Arm order rotated per
  (rep, item) as in `overthink_run.sh`.
- **Arms:**
  - `A`: no penalty.
  - `B`: `logit_bias` -2 on the marker set.
  - `C`: `logit_bias` -4 on the marker set.
- **Marker set:** the 20 single-token forms (with and without a leading space) of `Wait, But, Hmm, Actually,
  Alternatively, However, Hold, Oh, Maybe, Perhaps`: the class the KLD test scored (`marker_ids.json`). The bias
  applies to every generated token (thinking and answer), as in the source.

## Measures

- **Thinking length:** characters of `reasoning` per generation.
- **Outcome** (the runner's own grading): ANSWERED-CORRECT / ANSWERED-WRONG / ABSTAINED. NO-STOP is `finish ==
  length`.
- **Marker counts** in the reasoning text: penalized forms, and unpenalized substitutes (lowercase `wait`, `hmm`,
  `however`, `alternatively`, `actually`, and the phrases `let me reconsider`, `on second thought`).

Unit of inference: the **item** (16). Per model and penalty arm, the per-item statistic is
log(mean thinking chars in the arm / mean in A), averaged over reps. Test: exact sign-flip permutation over items
(minimum p = 3.1e-5).

## Predictions

| # | claim | test | conf |
|---|---|---|---:|
| M1 | The penalty shortens thinking at Q6_K | arm C / arm A geometric-mean thinking length < 0.85, p < 0.05 | 0.60 |
| M2 | No calibration cost | per model, arms B and C: answerable correct >= A - 2 (of 24), unanswerable WRONG + NO-STOP <= A + 2 (of 24) | 0.70 |
| M3 | The effect does not depend on bit depth (the KLD result's prediction) | arm C length ratio at IQ3_XXS within +/-0.10 of the ratio at Q6_K | 0.55 |
| M4 | The model substitutes | in arm C, penalized markers fall >= 90 % and unpenalized substitutes at least double vs A (both models pooled) | 0.50 |

**Reading, fixed now:**
- M1 and M2 true -> a free length control for `.73`; the next step is a speed and answer-quality test there.
- M1 true, M2 false -> the length comes out of calibration; do not deploy.
- M1 false -> this model routes around a token-level penalty (M4 says how).
- M3 false, with IQ3_XXS benefiting more -> contradicts the KLD receipt's reading and needs a closer look.

## Not established by design

16 items (a gate-sized set: fine for "does it break calibration", weak for small deltas), one model family,
`xhigh` effort only, lambda at two values, no accuracy set beyond CAL.
