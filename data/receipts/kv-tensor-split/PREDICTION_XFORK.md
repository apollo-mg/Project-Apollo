# Pre-registered predictions — cross-fork KV ladder (backlog N3)

**Written 2026-08-17 ~10:15 EDT, before the run started.** Scored against `RESULT_XFORK.md`.

## What is being tested

`RESULT_TWO_KV_BUGS.md` found two KV bugs on **buun_vbr `a8e5b5a38`** / `.73` / sm_60.
This runs the same matrix on **TheTom/llama-cpp-turboquant `f6124e9`** (the #295 merge
commit, built for sm_60 today) — same node, same model
(`unsloth-Qwen3.8-27B-Q6_K.gguf`, D=256, GQA 6:1), same flags, same detector, same probe
prompts as `~/kv_pin2.sh`.

The answer decides who the report goes to: buun alone, or buun *and* Tom, or upstream.

**Every arm pins `TURBO_AUTO_ASYMMETRIC=0`** except T8. Tom's fork silently upgrades K to
`q8_0` when the K type is turbo, `type_k == type_v`, and `gqa_ratio >= 6`
(`src/llama-kv-cache.cpp:147-161`). This model is exactly 6:1, so an unpinned turbo-symmetric
arm measures a configuration it did not ask for.

## Evidence gathered before predicting

Both are source facts read on the node, not guesses. They are why these predictions are
asymmetric rather than coin flips.

1. **Tom's `fattn.cu` enumerates `q8_0` K+V for every head dim.** Line 406:
   `FATTN_VEC_CASES_ALL_D(GGML_TYPE_Q8_0, GGML_TYPE_Q8_0)`, plus mixed pairs at 401/424 and
   the rest of the stock grid at 374-405. buun's D=256 table (`fattn.cu:2268-2284`) listed
   **only turbo types plus f16 pairings** — `q8_0` was absent, which was the mechanism
   hypothesis for Bug A.
2. **The Bug B assert site is shared.** `ggml-backend-meta.cpp` exists in Tom's tree
   (107 KB) with `GGML_ASSERT(ret.axis != GGML_BACKEND_SPLIT_AXIS_UNKNOWN)` at **line 535**
   against buun's **533** — a two-line offset in near-identical code. Bug B has a live site
   in this binary.

## Predictions

| # | arm | prediction | conf |
|---|---|---|---|
| X1 | **T2** `q8_0`+`q8_0` | **CLEAN — does not reproduce.** The dispatch entry buun lacks at D=256 is present here for all D. | **0.80** |
| X2 | **T3** `q4_0`+`q4_0` | **CLEAN.** Same reasoning; the stock grid is fully instantiated. Moves with X1 — if X1 is wrong this is too. | 0.75 |
| X3 | **T4/T5** mixed `q8_0`/f16 | **HARD ABORT — reproduces.** Same assert, same file, two lines apart, and this is a backend graph-split failure that `fattn`'s type coverage cannot rescue. | 0.70 |
| X4 | **T6** `q8_0`+turbo4 | **CLEAN.** Clean on buun; strictly better supported here. | 0.90 |
| X5 | **T7** turbo3 sym, guard **OFF** | **Visible damage.** Tom's own code comment cites turbo3 K at GQA 7:1 giving PPL 2887 vs 7.4 baseline; 6:1 is his stated threshold. | 0.60 |
| X6 | **T8** turbo3 sym, guard **ON** | **CLEAN, and the log prints the upgrade warning.** This is the arm that documents the silent rewrite. | 0.85 |
| X7 | **T1** f16 control | clean | 0.97 |

**Composite call: the two bugs separate.** Bug A is buun-specific; Bug B is shared. If that
holds, O3 splits into two reports with different audiences — a codec-coverage gap that is
buun's alone, and a split-axis assert that belongs to whoever owns `ggml-backend-meta.cpp`
in both trees.

## The instrument's known blind spot, stated in advance

The detector flags **collapse** (`maxrun > 200` or `< 12` unique characters), not quality.
Thresholds are the corrected ones — AFM-15 records that `maxrun > 40` flagged a legitimate
markdown table rule as degeneration.

This matters most for **X5**. A PPL blowup to 2887 would probably produce visible
degeneration, but it could equally produce fluent-looking wrong text that scores `ok`. **If
T7 comes back `ok`, that is not evidence the guard is unnecessary** — it is evidence this
instrument cannot see the damage the guard exists to prevent, and the question moves to a
KLD or perplexity panel. I am recording that now so the null is not over-read later.

## Also not established by this run

- **One model, one head dim.** D=256 throughout, so N1 (is the collapse D=256-specific?)
  stays open regardless of outcome.
- **Whether either bug is a regression** in either fork. Needs a bisect, not a matrix.
- **T9** (`-sm layer`, `q8_0` K+V) is a split-mode control only. On buun the collapse was
  split-independent, so a difference here would be new and would reopen the sharding
  hypothesis that P3 killed.
