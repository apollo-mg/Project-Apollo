# Result — the depth sweep's gate failed: per-request MTP depth is ignored. But depth 7 makes MTP a net loss for EXL3

**Run 2026-09-12, 18:12–18:35, on `.73`.** Pre-registered in `PREREG_EXL3_DRAFT_DEPTH.md` (`df56fcd`),
scored by `tools/score_exl3_depth.py`, committed with the prereg. Raw data in `depth/`. EXL3 campaign
test 6, ledger O5. **Prompted by Mark:** *"Perhaps less MTP depth then with these models that require
extra processing steps?"*

## The gate failed, so the test's own question is unanswered

**P-S0 is FALSIFIED for both arms.** Every request reported **545 drafted tokens for 256 predicted**, at
every requested depth (0, 1, 2, 3, 5, 7), in both arms. The requested depth changed nothing.

**The server used its CLI `--draft-max 7` throughout.** Working back from the counters: 256 predicted =
steps + accepted, so with 177 accepted there were ~79 steps, and 545 ÷ 79 ≈ **6.9 drafts per step**.

Per the prereg, **P-S1 through P-S4 are VOID.** The scorer prints them marked descriptive, where they
read as artifacts of a flat curve rather than findings. Identical counts *within* an arm are ordinary
greedy determinism — the same prompt, server and weights produce the same text, as test 1 also showed.

## What the source says, and the question it raises for buun

- `tools/server/server-schema.cpp:200` binds the request field `speculative.n_max` to
  `params.speculative.draft.n_max`.
- `common_speculative_n_max(spec, params)` (`common/speculative.cpp:6927`) routes any non-DFLASH type to
  `common_speculative_n_max(&params)`, which for `COMMON_SPECULATIVE_TYPE_DRAFT_MTP` returns
  **`spec->draft.n_max`** (`speculative.cpp:5352-5355`) — exactly the member the request writes.

So on paper the per-request value should reach MTP drafting, and on hardware it does not. **This is a
question for buun, not a bug report:** is per-request `speculative.n_max` meant to apply under
`--spec-type draft-mtp`? Until then, **depth is a server-level setting on this fork** and any depth
sweep needs a restart per point.

## The usable result: depth 7 against depth 3

This run set `--draft-max 7` with otherwise the daily driver's exact flags, so it is directly comparable
to test 1's depth-3 run — same binary, node, prompt, greedy sampling and 256-token reps.

| | MTP off | depth 3 | depth 7 |
|---|---|---|---|
| **EXL3 4.00bpw** | 11.22 t/s | 13.96 (**1.24×**) | 8.72 (**0.78×**) |
| **Q6_K** | 13.18 t/s | 22.27 (**1.69×**) | 14.44 (**1.10×**) |
| acceptance | – | ~0.69 | **0.325** |

- **At depth 7, MTP is a net loss for EXL3** — 0.78× of not speculating at all — while Q6_K is still
  slightly ahead at 1.10×.
- **Acceptance halves** from ~0.69 to 0.325, because later draft positions are rarely right, so the
  extra drafting is wasted work that still has to be verified.
- **This matches the fleet's existing Pascal finding** that MTP peaks around depth 3 and eventually goes
  slower than no speculation. What is new is that **EXL3 crosses below 1.0 well before GGUF does**,
  which is the direction Mark predicted: a format whose extra rows cost more should want less depth.

*(Descriptive: a cross-test comparison against test 1, not a preregistered claim.)*

## What is still unknown

**The curve between depths 1 and 5 — the actual question.** It needs a server restart per depth:
roughly 25 minutes for EXL3 at four depths (318 s to load each time off spinning disk) plus about 7
minutes for Q6_K. Named as a follow-up rather than run tonight.

## Deviations

- **`kv_bpv` read 16.0 at load for both arms again** — VBR's f16 entry tier, as in test 1.
- **My completion waiter fired early.** It matched an `ABORT` line left in the same appended log by the
  17:57 attempt, so it reported completion while the run was still going. No data was affected; later
  waiters match only the completion marker.
- **Load times: EXL3 317.7 s, Q6_K 35.8 s** — O10 again.
- **The dev-diary ledger lost its 18:05 run** to this window.
