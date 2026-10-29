# Pre-registration -- AbstentionBench-sub500: a frozen 500-item subset for release-day cards

**Registered 2026-10-28, before any subset number was computed.** Selection (`make_subset.py`) read only dataset, index,
label and a hash of each question, never a verdict; the check (`check_subset.py`) is committed with this file.

**Prior art checked:** `ledger_precheck.py "AbstentionBench subset stratified"` -> INDEX L571 (the fast subset reproduces
on llama.cpp; its judge reads the answer key) and L573 (the 27B, thinking on vs off, 2,004 pairs). **What this adds:**
a cheaper instrument, frozen by content hash, with its resolution stated before use, so a new model gets an AbstentionBench
row within a day (Mark's decision, 2026-10-28: AbstentionBench as an outside anchor next to our own instruments).

## The instrument: `AbstentionBench-sub500/norefs` v1

- **Items:** 500 of the 2,004-item fast subset (Meta's `fast-subset-indices.json`, sha256 `2ca7e91c...`, checkout
  `e291841`, FreshQA excluded as before). Strata are (dataset, should_abstain), 42 cells. Quotas are proportional by
  largest remainder, at least 1 per cell, so headline recall and precision estimate the fast subset's without weights.
  Within a cell, items are ranked by sha256("20261028:dataset:index"), first `quota` taken.
- **Frozen by content:** `subset_500.csv` stores dataset, index, label and the sha256 of each question (no item text: GPQA
  rule). Before every run, `make_subset.py --verify` re-hashes the export and refuses on any mismatch, so an upstream
  change cannot swap a question under the same index.
- **Protocol: Meta's, unchanged from the fast instrument.** The question is the only message, T 0.8, top_p 0.95, 4,000
  tokens. Thinking models use Meta's two-phase protocol, as the 27B's ON arm did. Judged by the norefs judge (no label, no
  references; Llama 3.1 8B Q8_0 on the 9070). This differs from M1's two modes (greedy plus vendor sampling) on purpose:
  it keeps the row comparable with the stored anchors and with Meta's method. Sub500 numbers are not comparable with
  fast-subset rows or with Meta's published table (versioning rule).

## Resolution, stated in advance (worst case, p = 0.5)

| card metric | n in sub500 | 95 % half-width |
|---|---|---|
| abstention recall | 218 | +-0.066 |
| missing-info recall | 43 | +-0.143 |
| false-premise recall | 27 | +-0.176 |
| abstention precision | the model's own abstentions | varies |

**Not expected to resolve:** effects the size of the 27B's thinking effect on the full set (recall -0.044). A null on
sub500 for an effect that size means "too small to see here", never "no effect". The two sub-metrics are coarse; the
card shows them with n.

## Check (`check_subset.py`), on the stored anchors LLAMA8, Q27OFF, Q27ON (norefs verdicts)

- **Joins are asserted:** all 500 subset items have a verdict in each table, and every label agrees.
- **PASS:** each anchor's full-set value of the four card metrics (12 values) lies inside its sub500 95 % Wilson
  interval.
- **Reported, not judged:** the Q27ON - Q27OFF paired recall difference on sub500 (bootstrap 10,000, seed 20261028) next
  to the full set's.
- **What a pass means:** the subset's item-sampling error is within its stated intervals on these verdicts. It is a
  sanity check, not a validation: the subset is a subsample of the same verdicts, and two of the three anchors are the
  same model.

## Fallback, registered now

If any of the 12 values falls outside, the instrument becomes `subset_1000` (same seed and ranking, containment asserted;
recall +-0.047, missing-info +-0.103, false-premise +-0.128), checked by the same rule. Never a reseed. If 1,000 also fails,
nothing is frozen, and the result is reported as it stands.
