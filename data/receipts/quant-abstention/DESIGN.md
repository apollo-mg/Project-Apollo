# Campaign design -- does quantization preserve "I don't know"? Knee vs method-shaped abstention curves on Qwen3.8-27B

**2026-09-26.** Design document, not a prereg. The pilot is registered in `PREREG_PILOT.md`. The main campaign is
registered separately **after** the pilot has sized it and validated the readout.

## The question

Every published quant comparison ranks files by KLD to BF16. None measures whether a quant still says "I don't
know". Our data hints that low-bit quants can fail in **opposite directions** at similar size:

| file | size | effort | answerable | unanswerable abstained | receipt |
|---|---:|---|---:|---:|---|
| AD IQ2_XS (imatrix PTQ) | 9.21 GiB | medium | **20/24** | **24/24** (timid: knowledge erased, then abstains) | `viability/RESULT_AD_QUANT_LADDER.md` |
| Bonsai 2 PQ2_0 (vendor ternary) | 7.2 GB | xhigh | 23/24 | **14/24** (confident: knowledge kept, facts invented) | `marker-penalty/RESULT_MARKER_PENALTY_BONSAI.md` |

**These are not comparable as they stand:** the efforts differ (L58: `xhigh` alone drops abstention 21 -> 13), and
there are 24 trials per cell. The campaign asks two things:
- **H-knee:** is there a size (effective scored bpw) below which abstention behaviour breaks, roughly the same
  for every method?
- **H-method:** at matched size, do methods differ from the ceiling in **different directions** (timid vs
  confident), making the curves method-shaped rather than a single knee?

## Instrument (one box, one binary)

- **All arms on `.194`,** buun at one commit, built sm_60. EXL3 runs correctly on Pascal (`exl3-on-pascal`), and
  the primary readout is prefill-only, so its speed is irrelevant. If any arm must run elsewhere, one bridge arm
  runs on both boxes.
- **Settings:** f16 KV, passed **explicitly** (buun defaults to VBR) and verified in the log. MTP off.
  `cache_prompt: false`. `-np 1`. `-sm layer`. Server restarted per arm, and the first request after load
  discarded.
- **Ceiling:** Q8_0 (27.05 GiB; KLD ~0.000 vs BF16 in `exl3-campaign/RESULT_EXL3_KLD.md`'s reference). BF16 is
  not used as the ceiling: its sm_60 path is doubtful.
- **One effort for everything.** The primary regime is **thinking off** (`enable_thinking: false`): one short
  answer per item, so every arm runs in minutes, and a clean answer-slot readout. A medium-thinking subset runs
  only if the pilot shows thinking-off does not reproduce the phenomenon. Thinking-off numbers are **never**
  compared with the medium-effort AD-ladder numbers.

## Readouts

- **R-slot (primary if the pilot validates it).** The prompt is rendered (thinking off) with `Exact Answer:`
  appended, and the next-token distribution is read.
  - `P_abs` = P(" UNKNOWN") + P(" Unknown") + P(" unknown"). " UNKNOWN" is a **single token** after
    `Exact Answer:` in this vocabulary, as are " UNESCO", " Regina" and " unknown"; numbers begin with a bare " "
    token. Checked 2026-09-26 with `llama-tokenize`, so there is no prefix collision with real answers.
  - It is continuous, deterministic and prefill-only.
- **R-gen.** A greedy thinking-off generation, 48 tokens, graded four ways:
  - **CORRECT;**
  - **WRONG;**
  - **ABSTAINED on unanswerable** (right);
  - **ABSTAINED on answerable**, a separate class: appropriate abstention on a hard item is not a wrong answer
    (the A1 amendment).

## Metrics (AFM-22 applies to the continuous readout too)

Quantization noise flattens distributions and can raise `P_abs` everywhere. So these are always reported
**separately**, and a uniform upward shift is **never** called better calibration:
- **Discrimination:** AUROC of `P_abs`, unanswerable vs answerable.
- **Timidity:** mean `P_abs` on answerable items, easy and hard separately.
- **Confabulation:** mean (1 - `P_abs`) on unanswerable items, and the R-gen WRONG rate on unanswerable items.
- **Knowledge:** R-gen CORRECT on answerable items.
- **Direction of failure vs the ceiling:** *timid* = timidity up and confabulation down, *confident* =
  confabulation up with timidity flat, *noisy* = discrimination down with both flat.

## Corpus (A1 spec + its 2026-09-07 amendment; built from sources, not from memory)

**Three arms:**

| arm | construction | obscurity |
|---|---|---|
| **E** easy answerable | Wikidata single-valued facts (a year signed, a capital, a publication year, a composer, ...) | high Wikidata sitelink count |
| **H** hard answerable | the same templates | **low sitelink count**, a model-independent obscurity measure. Items are *not* selected on any model's accuracy; the pilot only checks the arm lands in a useful range at the ceiling |
| **U** unanswerable | the same templates with **plausible** invented members of real categories, real authors with invented works, and false premises on real entities (AFM-22: no orthographic tells; an obvious fake tests a different thing) | matched in category to E/H |

- **Every gold has a source** (the Wikidata QID and property).
- **Every fake has a nonexistence record:** no Wikidata entity with that label (`wbsearchentities`), plus no hits for
  the exact phrase in a web search.
- **Mark spot-checks a random 10 %** of each arm before the pilot runs.
- Items are authored fresh (no public calibration set), so there is no training contamination.
- **Size:** the pilot uses 40 per arm (120). The main size comes from the pilot's measured discordance and
  variance. A1's sizing is ~240+ per arm for binary McNemar; the continuous readout may need fewer.

## Arms for the main campaign (inventory 2026-09-26; x-axis = scored bytes, MTP head and mmproj subtracted)

| method | rungs available (GiB on disk) | category |
|---|---|---|
| AD (imatrix IQ) | IQ2_XS 9.21, IQ3_XXS 11.25, IQ3_S 12.09 | PTQ |
| unsloth UD | Q2_K_XL 9.15, IQ2_M 9.61, IQ3_XXS 11.10, IQ4_XS 13.27 | PTQ (mixed recipe) |
| ISTA GSQ-RCO | IQ2_XS 8.17, IQ3_XXS 9.73 (+IQ2_S, IQ3_S to fetch) | PTQ (their method) |
| Agention AP | to fetch: IQ2_S, IQ3_XXS, IQ3_XS, IQ3_S | PTQ ("non-uniform assignment + error correction") |
| APEX | I-Nano 10.47, I-Mini 12.99 | PTQ |
| EXL3 | 2.5 / 3.0 / 3.5 / 4.0 / 5.0 bpw | trellis PTQ |
| **Bonsai 2** | PTQ1_0 5.54, PQ2_0 6.71 | **its own category: vendor ternary, method undisclosed.** The whitepaper does not state training vs PTQ; 98.2 % benchmark retention at 1.76 bpw is implausible for training-free ternary, so probably trained or distilled. It is **not** used as evidence about PTQ methods |
| ceiling | Q8_0 27.05 | -- |

**Knee range:** at least 3 rungs per method in roughly 2-3.5 bpw, where the table is densest. Q4-Q8 coverage adds
little.

**Decision rules** (sketched here, registered in the main prereg):
- **Knee:** a breakpoint in discrimination vs scored bytes, common across methods within a CI.
- **Method-shaped:** two PTQ methods in the same byte bin differ from the ceiling in opposite directions, CI
  excluding zero.

## Not in scope

- Other model families.
- Thinking-mode behaviour beyond the fallback subset.
- Why a method fails in a given direction (mechanism), beyond the readout's confidence signature.
