# Hemmingway-1 matches stock Qwen3.8-27B at technical writing: a blind near-tie, zero fabrications in either, identical diary quality

**2026-09-24**, `.194`, bartowski Q5_K_M pair (352 bytes apart, identical chat template `c3cf9e34`) plus
stock Q6_K for the mechanical scores. 23 tasks: 20 technical-writing tasks and 3 real diary windows.
Prereg `PREREG_HEMM_TECHWRITING.md` (`c6b725d`). Scorer `analyze_techwriting.py` -> `RESULT_techwriting.json`.
Blind ratings by Mark on the published page (`raw/ratings.json`); the side key is `raw/ab_mapping.json`, committed
only after rating.

## Blind preference (Mark, 20 tasks, S5 vs H5)

| | count |
|---|---:|
| Hemmingway preferred | **5** |
| stock preferred | **3** |
| tie | **12** |

Exact sign test p = 0.73. Mark's own read before unblinding: *"for technical writing, I think it was pretty close."*
It was.

**The blinding leaked, partly because of my page.**
- "Which is Hemmingway?": right **10**, wrong **4**, unsure **6** (p = 0.18 vs chance). That's better than chance
  but not decisively.
- Mark named two tells:
  1. **Fewer bullets and paragraphs.** Real: Hemmingway 76 bullets / 195 paragraph blocks vs stock 92 / 209.
  2. **Unexplained strikethroughs.** An instrument artifact. Hemmingway writes approximations with a tilde more
     often ("~296 prompt tokens ... ~628"): 15 tildes vs 10. The page's markdown renderer (marked, GFM) strikes
     through text between two SINGLE tildes, so 4 Hemmingway spans rendered struck-through against 1 for stock.
     The style difference is real; the visible strike was my page's. **Fix for any future blind page:** escape `~`
     or disable single-tilde strikethrough.
- Split by whether Mark's guess was right: when right, H5 4 vs S5 1; when wrong or unsure, H5 1 vs S5 2. With n=8
  decided, that is not interpretable. Length did not drive preference: the longer draft won 4 of 8.

## Mechanical scores

| | stock Q5 (S5) | Hemmingway Q5 (H5) | stock Q6 (S6) |
|---|---:|---:|---:|
| numbers absent from the source (12 source tasks) | 1 | 3 | 2 |
| ...of which actual errors (hand-checked) | **0** | **0** | **0** |
| explainer key facts hit (of 20) | 17 | 18 | 18 |
| explainer misconceptions | 0 | 0 | 0 |
| diary: unverified-claim tags (3 real windows) | 0 | 0 | 0 |
| diary: `classify()` passes / bad headings | 3/3, 0 | 3/3, 0 | 3/3, 0 |
| words, 20 writing tasks | 6,918 | **6,294** (-9 %) | 7,012 |
| reasoning chars | 63,294 | 51,783 (-18 %) | 62,117 |
| finish = stop | 23/23 | 23/23 | 23/23 |

Every number that was not in its source is a correct derivation:
- 35 % is 35.2 % rounded;
- 27 % is 552/2048;
- 3.9 GiB is 3,903 MiB;
- 20 pp is 55.0 - 35.2.

**None of the three invented a fact** on these tasks.

## Decision rule (as registered)

1. Preference: H5 5 > S5 3. **Pass** (the registered bar is "wins more"; it is effectively a tie).
2. Faithfulness: H5 3 <= S5 1 + 2. **Pass.** All are correct derivations, so both are really 0.
3. Explain: 18 >= 17 - 2, and misconceptions 0 <= 0. **Pass.**
4. Diary: 0 <= 0 tags, and classify passes on all 3. **Pass.**

**Per the rule: swap is acceptable.** The honest reading is narrower. **Hemmingway is not worse at technical
writing** (near-tie, no fabrication, same diary quality), and it is ~9 % shorter with ~18 % less reasoning.
The swap is a style choice, not a quality upgrade, on this kind of work.

## Deviations and instrument defects (disclosed)

- **The invented-number parser had bugs; fixed post hoc and applied identically to all arms.**
  - v1 missed numbers glued to units in the source (`544M`, `552.00`) and split thin-space thousands (`25 088`).
  - v1 totals were 11 / 5 / 16; v2 is 1 / 3 / 2, and the hand check found 0 real errors.
  - The v1 numbers remain in `RESULT_techwriting.json`; v2 totals are in `raw/invented_numbers_v2_totals.json`.
- **The invented-identifier metric is VOID.** It counted any inline-code span absent from the source, and most of
  those were formatting of prose fragments, not identifiers (S5 56, H5 47, S6 73).
- **S6 is not a clean quant comparison.** The stock Q6_K file ships a *different chat template* (`12827f24`) from
  the bartowski Q5 pair. It differs from S5 in quant and template, so read it as "the kind of file the daily driver
  runs", not a quant effect. Its scores are in line with S5.
- One sample per task at temp 0.6. A near-tie on 20 tasks cannot rule out a small style preference either way.

## What this adds

Prior receipts showed Hemmingway keeps agentic judgement and is intrinsically terse. This adds **technical writing
and faithfulness**, where it is no worse, and the **production diary task**, where it is identical. That covers
the one objective consumer of `.73`'s model.

## Not established

One quant pair, one rater (the person making the decision, who knew the tune's reputation), 20 tasks, and English
technical prose only. Everyday-message quality, which the card actually claims, was not tested.
