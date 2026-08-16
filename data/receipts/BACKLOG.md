# Backlog — open threads, with cost and what blocks them

Sessions here turn into rabbit holes. That is usually productive — the
`reasoning_effort` finding came out of a detour off a detour — but the cost is that
five other threads get dropped mid-flight and quietly forgotten.

This is the third of three files that exist so work survives its session:

- `FAILURE_MODES.md` — how we get things wrong (check before designing)
- `INDEX.md` — what we already know (grep before investigating)
- `BACKLOG.md` — what we owe (this file)

**Cost column** is wall-clock on idle hardware unless it says otherwise. Most of these
cost tokens only to start and interpret, which is the actual scarce resource.

---

## Blocking — a claim is currently unsafe to quote until these run

| # | thread | cost | why it blocks |
|---|---|---|---|
| B1 | **Re-run the speculation losslessness test with `cache_prompt:false`** | ~20 min | `RESULT_SPECULATION_IS_NOT_BIT_EXACT` ran with prompt caching at its default `true`. `MTP_CACHEPROMPT_FALSIFICATION` (07-30) concluded MTP *is* deterministic at temp 0 and the instability was the caching interaction. The receipt is marked PROVISIONAL and is cited by two others. |
| B2 | **Reconcile the parse-rate disagreement** | minutes | `run_hle_mini.py` parses `content` only (20 %); `rejudge.py` parses `content + reasoning` (40–50 %). Two of our own tools disagree on the same traces. Stricter reading is probably right — truncated reasoning holds *drafts*, not conclusions — but "probably" is not quotable. |
| B3 | **Finish the KV degradation pin (P1–P5)** | ~40 min | Arm B showed `q8_0` K+V degenerating 5/5 on the first request, but both arms carried `-sm tensor` **and** MTP, so the general claim was overstated. Mark runs K=q8_0/V=turbo4 daily without trouble. P5 (his pair, current build) discriminates codec bug from build regression. Script staged at `~/kv_pin.sh` on `.73`. |

## Cheap and high-value

| # | thread | cost | note |
|---|---|---|---|
| C1 | **HLE effort ladder with repeats** — {low, medium, xhigh} x 5q x 3 reps | ~2 h | Answers Mark's "medium is the sweet spot" hypothesis *and* measures run-to-run variance, which we currently have none of. At temp 1.0 repeats are genuine samples, unlike `headlab`'s deterministic replays. The 80 % parse figure is **one draw**. |
| C2 | **Does Mark's daily VBR workload ever leave entry tier?** | minutes | `/slots` exposes `kv_bpv`. Receipts show VBR enters at f16 and degrades only under pressure, and in past tests *never engaged* (`kv_bpv: 16.0` throughout). If his sessions never pressure it, his "VBR is sharper" experience may be "VBR is f16". |
| C3 | **Build a true upstream `llama.cpp` reference binary** | ~30 min build | There is **none** on either box — `llama_stock_ref` carries laguna patches despite the name. Blocks every "does this reproduce on stock" question. `DETERMINISM_ROOT_CAUSE` tested genuine upstream `0e4a03622` in July; that checkout may still exist. |
| C4 | **empero-ai/Qwen3.8-9B: real distillation gain or extraction artifact?** | ~1 h | Card claims MMLU +26 pp strict-match over Qwen3.5-9B, but the *base* scores 0.251 strict — chance for 4-way MC — while GSM8K (extraction-robust) went **down** 0.015. Our harness reports parse rate separately from accuracy, which is exactly the instrument `lm-evaluation-harness` lacks. Base model already on disk. |

## Substantial experiments

| # | thread | cost | note |
|---|---|---|---|
| S1 | **Full `subset_v1` (200q) at `reasoning_effort=low`** | ~4.6 h | First real HLE number for a local 27B. Was 8.1 h projected at `xhigh` with a 0 % parse rate, so it was never viable before. |
| S2 | **DFlash on Pascal, instrumented with `nvprof`** | ~2 h | Approved. Tests whether the batched-drafter advantage inverts on compute-bound hardware. 228 W against a 300 W cap leaves headroom for occupancy to actually rise. `achieved_occupancy` / `sm_efficiency` / `dram_utilization` measure the mechanism directly instead of inferring it from t/s. |
| S3 | **TCQ throughput-per-fidelity: Pascal vs RDNA4** | ~3 h | `turbo3_tcq` wins on margin (76/120 → 94/120 with depth). But Viterbi decode is sequential — TCQ spends compute to save bits, and Pascal at 150 W is compute-bound. Prediction: the margin win may not survive as a *throughput* win there, while looking excellent on RDNA4. Fleet spans both regimes. |
| S4 | **VBR rate-distortion curve** | ~3 h | VBR has no fixed operating point; point comparisons against static codecs are category errors, and one already produced a wrong conclusion ("VBR beats turbo4 at 100 % fill" — artifact of unequal budget). Right instrument: fidelity vs **achieved `kv_bpv`** across fill levels, matched on achieved bitrate. |
| S5 | **bartowski's Q8_0-body draft-head question** | ~1 h | Offer posted, awaiting reply. Our head-isolation used an `IQ3_XXS` body — his "doesn't matter much" regime. His actual uncertainty is about a `Q8_0` body, which we never built. |

## Contributions / outward

| # | thread | status |
|---|---|---|
| O1 | AtomicChat discussion #65 — `AD-IQ3_S` head built with no importance data | **posted, awaiting reply** |
| O2 | bartowski thread — Q8_0 MTP head offer | **posted, awaiting reply** |
| O3 | **buun: `q8_0` KV degeneration on Pascal** | pending B3 — needs the pin result before reporting |
| O4 | **buun: template v3 for Qwen3.8** | 3.6→3.8 rewrite dropped 4 of his 25 fixes (`\| safe`, `loop.previtem`, 9 `raise_exception` sites, `developer` role). Worth telling him; a v3 would have users immediately. |
| O5 | GGML sm_60 issue | filed, **open and unconfirmed** |

## Long-standing / low urgency

| # | thread | note |
|---|---|---|
| L1 | Prompt-cache prefix fix, `apollo_server.ts:449-479` | Diagnosed, never implemented. Predates this campaign. |
| L2 | HLE seed policy — canonical id set vs own-seed | Mark's call. Canonical makes numbers comparable and concentrates leak risk; own-seed is safer and costs the paired power. `build_subset.py --seed N` supports either. |
| L3 | `.194` HumanEval+ ladder | Long-running. Status unchecked in a while. |
| L4 | A judge stronger than Qwen3.5-9B | Current judge validated 5/6 with its miss in the conservative direction, so numbers are floors. A cloud judge would send HLE gold answers to a third party — against the canary and our own hygiene rules. Prefer a larger local model. |
