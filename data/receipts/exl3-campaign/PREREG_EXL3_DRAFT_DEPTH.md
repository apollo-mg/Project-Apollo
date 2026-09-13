# Prereg — the right MTP depth for EXL3 (EXL3 campaign, test 6, ledger O5)

**Written 2026-09-12 ~17:10, before any depth-sweep data.** Prompted by Mark: *"Perhaps less MTP depth
then with these models that require extra processing steps?"*

## Question

Test 1 measured MTP buying EXL3 1.24× and GGUF 1.69× at depth 3, with identical acceptance. If EXL3's
extra verify rows cost more than GGUF's, **its optimal draft depth should be lower.** A cost model fitted
to test 1's two points puts EXL3's marginal cost per extra row at 0.49 against GGUF's 0.27, and predicts
EXL3 peaking near depth 2 for a gain of about 2-3%. **That is a sketch from two points and an assumed
acceptance decay. This test measures the curve.**

The daily driver runs `--draft-max 3` today. If EXL3 is ever deployed, this test says what to set.

## Setup

- **Node:** `.73`, both P100s, wake proxy paused with a dead-man timer, orchestrated by
  `orchestrate_depth.sh`, which waits for test 4 to finish.
- **Binary:** QUAL (buun `9ae8f0f40` + e8m0 guard), as in tests 1, 3 and 4.
- **Flags:** the daily driver's exact command **except `--draft-max 7`** instead of 3, so that the server
  permits every depth this test requests. Port 8190.
- **One server per format,** with depth varied **per request** via `speculative.n_max`
  (`tools/server/server-schema.cpp:200`). No reloads between depths.
- **Arms:** **X** = EXL3 4.00bpw, **Q** = the daily driver's Q6_K.
- **Depths:** 0, 1, 2, 3, 5, 7. Three reps each, the same speed prompt as test 1, 256 tokens, temperature
  0 with `top_k` 1, `ignore_eos`, no prompt cache.

## Measures

- **Decode** is the median `predicted_per_second` over an arm's 3 reps at a depth.
- **Gain(k)** is decode at depth k ÷ decode at depth 0.
- **Acceptance(k)** is Σ `draft_n_accepted` ÷ Σ `draft_n` at that depth.
- **Best depth** is the depth with the highest median decode.

## Predictions

| id | prediction |
|---|---|
| P-S0 | **Gate.** The per-request field works: for each arm, `draft_n` at depth 7 is at least twice `draft_n` at depth 1. If not, the field is inert for MTP, every result below is **VOID**, and the test must be redone with a server restart per depth |
| P-S1 | EXL3's best depth is ≤ 3 |
| P-S2 | Q6_K's best depth is ≥ 3 |
| P-S3 | EXL3's gain at its best depth is < 1.4× |
| P-S4 | At every depth ≥ 1, EXL3's gain is below Q6_K's |

**Descriptive:** the full curve for both arms, and acceptance against depth — acceptance should fall as
depth grows, since later draft positions are harder.

## Declared in advance

- **Depth 0 is the baseline** and is assumed to disable drafting. If `draft_n` at depth 0 is not zero,
  the baseline instead comes from test 1's MTP-off arms (Xn 11.22, Qn 13.18 t/s greedy), and that
  substitution is reported.
- **The server runs `--draft-max 7`, not the daily driver's 3.** This test measures a curve, not the
  deployment number; test 1 holds that.
- **One prompt, 256 tokens, three reps per point.** A speed estimate, not a distribution.
- **This is a matched comparison across depths within one server process,** so a depth-to-depth
  difference is not confounded by loading, but the two arms are separate processes.

**Scorer:** `tools/score_exl3_depth.py`, committed with this prereg.

## Amendment 3 — 2026-09-12 ~19:55: redo it with a server restart per depth

**The per-request method is dead.** Attempt 1's gate (P-S0) showed `speculative.n_max` is ignored under
`--spec-type draft-mtp`: every requested depth drafted ~7 per step, the server's CLI value
(`RESULT_EXL3_DEPTH.md`). Depth is a server-level setting on this fork, so the curve needs a restart per
point.

- **Method:** one server per (arm, depth), started with `--draft-max k`, otherwise the daily driver's
  exact flags. Everything else — prompt, greedy sampling, 256 tokens, three reps — is unchanged.
- **Depths: 1, 2, 3, 5.** Four points rather than six, because each EXL3 load costs 318 s off spinning
  disk. Depth 7 is already measured (attempt 1) and depth 0 comes from test 1's MTP-off arms.
- **Baselines are test 1's MTP-off figures:** EXL3 11.22 t/s, Q6_K 13.18 t/s greedy, measured on the same
  node, binary, flags and prompt. **That is a cross-test baseline** and is declared as such.
- **Arms:** `X` = EXL3 4.00bpw, `Q` = Q6_K.

| id | prediction |
|---|---|
| P-S5 | **Gate.** Depth reaches the model: drafted tokens per predicted token at depth 5 exceed those at depth 1 by at least 1.5×. If not, the method failed again and everything below is VOID |
| P-S6 | EXL3's best depth is ≤ 3 |
| P-S7 | Q6_K's best depth is ≥ 3 |
| P-S8 | EXL3's gain at its best depth is below 1.4× |
| P-S9 | At every depth, EXL3's gain is below Q6_K's |

**Declared:** the earlier P-S0 to P-S4 stay VOID and are not rescored. Attempt 1's depth-7 point is
carried into the receipt's curve as a fifth point, measured under the same flags with a different server
lifetime.

**Driver:** `exl3_depth_restart.py`. **Scorer:** `tools/score_exl3_depth_restart.py`.
