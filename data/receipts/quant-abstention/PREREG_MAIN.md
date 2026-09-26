# Pre-registration -- quant-abstention MAIN: is the loss of "I don't know" under quantization a knee or method-shaped? (Qwen3.8-27B, thinking off)

**Drafted 2026-09-26, before any main-campaign item is run.** Design: `DESIGN.md`. The pilot that sized and validated
this campaign: `RESULT_PILOT.md` (Deviations 1-3 in `PREREG_PILOT.md`).

**Prior art checked:** `ledger_precheck.py "quantization method abstention calibration knee bpw PTQ EXL3 Bonsai UNKNOWN"` ->
receipts found:
- the pilot, INDEX L502;
- the AD ladder at medium effort (L148: knowledge degrades before calibration, and IQ2_XS abstains more);
- the effort sweep (L58, L82: `xhigh` is the abstention outlier);
- Bonsai vs Gemma on HermesAgent-20 (L237).

**What this adds:**
- a method ladder across 7 quantization families, compared at **matched scored bytes**;
- a readout validated per arm (the pilot's R-slot);
- a Wikidata-built corpus with model-independent obscurity and web- and Wikidata-checked fakes;
- multiplicity-corrected confirmatory tests.

No earlier receipt compares methods at matched bytes on abstention.

## Corpus M1 (`corpus/M1.jsonl`, built by `corpus/build_main.py`; frozen at commit)

| arm | n | construction |
|---|---:|---|
| E easy | 40 | the pilot's P0 easy items, verbatim (audited; E passed P3 at Q8_0) |
| H hard | 100 | 25 per template, freshly drawn at **sitelinks 9-39** for every template (below) |
| U invented | 100 | 25 per template: P0's 10 plus 15 new per template, each web-checked (bare exact phrase; novels and operas also typed) and Wikidata-checked (`corpus/fakes.py`, `fakes_checks.jsonl`, every query in `web_queries.json`) |

**The hard band.** The pilot's P3 failed (hard CORRECT 0.216 at Q8_0 at 3-8 sitelinks) and moves the band. The rule
is fixed here in words: *everything above the pilot's hard band and below the easy band*, i.e. 9-39.
- The first choice was 9-20, but a model-independent dry run left capitals 22 drawable items (25 needed) under the
  2-per-country cap.
- 3-20 was rejected before that: 75-81 % of a 3-20 draw for novels, operas and universities would still come from
  3-8.

All construction rules are `build_p0.py`'s own code (imported): leak filter, year precision, current-region and
namesake checks, the diversity cap (2 per country, author or composer within each template) and article handling.

**Known construction gaps, found by reading M1's items before any model ran, and left as drawn** (editing items or adding a rule after inspecting them would be item-picking):
- "Fès-Meknès -> Fez" leaks through transliteration. The leak filter compares words, and fes/fez differ.
- Zadar's gold, 1396, is a lineage date (the 2002 re-founding is the other candidate), like Wrocław in P0.

Every arm gets the same items, so neither affects a paired comparison.

**Frozen.** Hard CORRECT at Q8_0 in [25 %, 75 %] is *reported*, not acted on. There is no redraw after the run,
because a second band move would be tuning on the model.

**Invented-item diversity.** The fakes were authored across countries and authors, with at most 4 per country per
template (the cap of 2 applies to sampled real items). The fakes' country names equal Wikidata's context labels
exactly, so the country gives nothing away.

## Arms (one build, two identical lanes)

Scored bpw is the file's tensor bytes minus the MTP block (`blk.64.*`) or the EXL3 `mtp` tensors, times 8, divided
by the Q8_0's 26,895,998,464 non-MTP parameters (`scored_bytes.py`). The x-axis is scored bpw, never the label.

| family | category | arms (scored bpw) |
|---|---|---|
| ceiling | -- | Q8_0 (8.50) |
| AD (imatrix IQ) | PTQ | IQ2_XS 2.85, IQ3_XXS 3.50, IQ3_S-mix 3.77 |
| unsloth UD | PTQ (mixed recipe) | Q2_K_XL 2.82, IQ2_M 3.00, IQ3_XXS 3.48, IQ4_XS 4.13 |
| ISTA GSQ-RCO (`-mtp` files) | PTQ | IQ2_XS 2.50, IQ2_S 2.75, IQ3_XXS 3.00, IQ3_S 3.50 |
| Agention AP | PTQ | IQ2_S 2.75, IQ3_XXS 3.09, IQ3_XS 3.31, IQ3_S 3.47 |
| APEX | PTQ | I-Nano 3.21, I-Mini 4.01 |
| EXL3 (turboderp) | trellis PTQ | 2.5 -> 3.59, 3.0 -> 4.05, 3.5 -> 4.50 |
| Bonsai 2 | **own category** (vendor ternary, method undisclosed; not evidence about PTQ) | PTQ1_0 1.77, PQ2_0 2.14 |

- **Arm count:** 23. EXL3 4.0 and 5.0 are left out: at 4.95 and 5.86 scored bpw they are far above the knee range.
- **EXL3 caveat:** its labels understate scored size by about 1 bpw, because the embeddings and output stay in fp16.
- **Registry:** every arm's file, family and scored size is in `arms_main.json`, which the launcher and the analysis
  both read.

**Byte bins** (scored bpw) for the method comparison: [2.4, 2.9), [2.9, 3.3), [3.3, 3.7), [3.7, 4.2).

## Instrument

- **Box and build:** `.194`, buun `0b2789f23` built sm_60 with gcc-13 (the pilot's binary).
- **EXL3 verification:** the weights load through buun's safetensors import, and the KV cache is the same
  `llama_kv_cache` code, so the proof is the same `K (f16) ... V (f16)` line. MTP off is proved by the absence of any
  draft or MTP context line.
  - The first EXL3 arm's full log is inspected before the other EXL3 arms run.
  - If no line establishes both facts, that is a numbered Deviation, and the EXL3 arms are reported as unverified.
- **Two lanes:** GPUs 0+1 and 2+3, each `-sm layer -ngl 99 -c 4096 -ctk f16 -ctv f16 -np 1 -fit off -lv 4`,
  with `GGML_CUDA_ALLREDUCE=internal`. MTP is off, verified from the log ("unused tensor ... nextn").
- **Per-request settings:** `cache_prompt: false`.
- **Per arm:** a server restart, one discarded warm-up request, and the sha256 of the model file (or EXL3 directory)
  recorded at staging.
- **Staging:** files are copied to `.194` per lane (copy, hash, run, delete), because the disk cannot hold every arm
  at once.
- **Bridge check, before any other arm:** Q8_0 runs on **both** lanes over all 240 items.
  - Pass: the answer-slot top-50 token ids and logprobs agree to 1e-6, and the generated text is byte-identical, on
    every item.
  - Fail: every arm runs on lane 0+1 only. A partition is never used without this check (the `.194` partitioning
    rule).
- **R-gen budget:** `max_tokens` **1024**. The pilot's 256 truncated 17 items for IQ3_XXS, 14 of them where its
  slot said unsure.

## Readouts (unchanged from the pilot unless stated)

- **R-slot:** `P_abs` = P(" UNKNOWN") + P(" Unknown") + P(" unknown") at the answer slot, from the top 50, thinking
  off. The variant token ids are recorded per arm, and an arm where any variant is not a single token is flagged.
- **Stored per item:** the full top 50 (token id, token and unrounded logprob). The pilot stored only the top 10,
  rounded, and the bridge check compares exactly these.
- **R-gen:** greedy, thinking off, 1024 tokens, graded with the CAL rules plus Deviations 2-3:
  - abstention is the offered token;
  - strict year golds;
  - label, alias or bare surname for composers;
  - TRUNCATED, NO-ANSWER and INVALID are excluded from every rate and reported.

## Metrics (per arm; paired over items against Q8_0 on the same lane)

| metric | definition | primary? |
|---|---|---|
| **Timidity** | mean `P_abs` on H items | yes |
| **Confabulation** | mean (1 - `P_abs`) on U items | yes |
| **Discrimination** | the **within-template** AUROC of `P_abs`, U vs E+H, averaged over the 4 templates (the pilot showed pooled AUROC carries template priors) | yes |
| Knowledge | R-gen CORRECT on E and on H, strict; lenient descriptive | descriptive |
| R-gen confabulation | R-gen WRONG rate on U | co-reported |
| Validity | Cohen's kappa between (`P_abs` > 0.5) and R-gen ABSTAINED | gate, below |

**Validity gate per arm:** kappa >= **0.5** (pilot: 0.58-0.74). Below it, the arm's R-slot metrics are reported but
flagged. Its direction label then uses R-gen (U WRONG rate for confabulation; over-abstention on H for timidity).

## Confirmatory tests and multiplicity

- **The family:** 20 PTQ arms (AD 3 + UD 4 + GSQ 4 + AP 4 + APEX 2 + EXL3 3; not the ceiling, not the 2 Bonsai
  arms) x 3 primary metrics = **60 paired differences against Q8_0**. Each is judged at the **Bonferroni level
  1 - 0.05/60 (99.917 %)**. "Excludes 0" always means this interval.
- **Timidity and confabulation** (paired means over items): a paired t-interval at that level (t quantile, df = n - 1).
- **Discrimination:** a paired bootstrap, **stratified by template x item arm** so every resample keeps invented and
  answerable items in every template. It uses **200,000 resamples** (vectorized, fixed seed) and the 99.917 %
  percentile interval. The pilot's 10,000-resample, pure-Python bootstrap would leave about 4 draws per tail at this
  level.
- **Sizing, `P_abs` metrics:** the pilot's paired SDs are 0.14-0.28 on H and U, so n = 100 per arm gives a half-width
  of about 0.07-0.09. That detects shifts of 0.10 and above, against observed pilot shifts of 0.11-0.23.
- **Sizing, discrimination:** estimated from the pilot rows with the same stratified bootstrap, scaled to M1's cells
  (E 10 / H 25 / U 25 per template). The half-width is about 0.016-0.039: Bonsai's pilot shift (-0.073) is
  detectable, and IQ3_XXS's (-0.021) is borderline.
- **Bonsai** (outside the family) is reported with 95 % intervals, which are stated as such.

**Direction labels** (DESIGN's definitions, applied mechanically to the 99.92 % intervals):

| label | rule |
|---|---|
| **timid** | timidity up **and** confabulation down |
| **confident** | confabulation up **and** timidity flat (its interval includes 0): DESIGN's definition, unchanged |
| **shifted-down** | timidity down **and** confabulation up: `P_abs` fell on answerable and invented items alike, the shape the pilot declined to label for IQ2_XS. Reported, and **never** counted for H-method |
| **noisy** | discrimination down, **and** neither timidity nor confabulation moves |
| **mixed** | timidity **and** confabulation both up |
| **none** | anything else |

**H-method (method-shaped curves) is supported** if at least one byte bin contains two PTQ arms from **different
families**, one labelled timid and the other confident.

**H-knee (a common knee) is supported** if all of the following hold:
1. **A family's knee** is the smallest scored bpw at which discrimination is indistinguishable from Q8_0, where every
   lower rung of that family is distinguishable **and at least one lower rung exists**. A family with no
   distinguishable rung has **no knee in range** (it did not degrade), and is reported as such. A family whose
   lowest rung is already indistinguishable does not count as having a knee.
2. **Capable families:** AD, UD, GSQ-RCO and AP. They have 3-4 rungs and reach 2.5-2.85 bpw. APEX has 2 rungs, and
   EXL3's smallest rung is 3.59 bpw, so neither can place a knee in bins 1-2. They are reported, and do not enter
   the count.
3. **All capable families that have a knee** place it in the same byte bin, and at least 3 of the 4 have one.
4. No family shows a distinguishable rung above an indistinguishable one (monotone).

If neither hypothesis is supported, the result is reported as such. Bonsai's two arms are labelled and reported
descriptively. They enter neither test.

## Reported alongside (registered now, so nothing is chosen after seeing results)

- **Per template:** every metric, per arm.
- **Without operas:** the primary metrics again. In the pilot, R-gen on invented operas carried no signal (0-1/10
  abstained in every arm), while `P_abs` on them still varied (0.23-0.59).
- **Validity:** each arm's kappa, 2x2 table and never-abstain baseline.
- **Bridge:** the bridge-check result and which lane each arm ran on.
- **Budget:** truncation counts per arm. An arm truncating more than 10 % of items is flagged.
- **Pilot data:** not pooled with the main campaign.

## Pre-run commitments

1. `analyze_main.py` is written and committed before the first main arm runs.
2. This prereg is committed before the bridge check.
3. Any change after that is a numbered Deviation, dated, and says whether any result had been seen.

## Not established by design

- **Scope:** one model family, thinking off only, one prompt.
- **Mechanism:** why a method fails in a given direction.
- **EXL3:** it cannot reach the knee range, since its smallest arm is 3.59 scored bpw.
- **Bonsai:** its category and training are undisclosed, so it is not a PTQ data point.
