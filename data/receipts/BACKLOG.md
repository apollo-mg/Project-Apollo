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
| ~~B1~~ | ~~Re-run the speculation losslessness test~~ **DONE 08-18** — swept both ways. MTP instability falsified (was caching); the 0/12 off-vs-speculative deviation SURVIVES. PROVISIONAL lifted. | — | `RESULT_SPECULATION_IS_NOT_BIT_EXACT` ran with prompt caching at its default `true`. `MTP_CACHEPROMPT_FALSIFICATION` (07-30) concluded MTP *is* deterministic at temp 0 and the instability was the caching interaction. The receipt is marked PROVISIONAL and is cited by two others. |
| B2 | **Reconcile the parse-rate disagreement** | minutes | `run_hle_mini.py` parses `content` only (20 %); `rejudge.py` parses `content + reasoning` (40–50 %). Two of our own tools disagree on the same traces. Stricter reading is probably right — truncated reasoning holds *drafts*, not conclusions — but "probably" is not quotable. |
| ~~B3~~ | ~~Finish the KV degradation pin~~ **DONE 08-16** — see `kv-tensor-split/RESULT_TWO_KV_BUGS.md`. Two bugs found; every stock quantized KV codec collapses, every buun codec works. | — | Arm B showed `q8_0` K+V degenerating 5/5 on the first request, but both arms carried `-sm tensor` **and** MTP, so the general claim was overstated. Mark runs K=q8_0/V=turbo4 daily without trouble. P5 (his pair, current build) discriminates codec bug from build regression. Script staged at `~/kv_pin.sh` on `.73`. |

## Cheap and high-value

| # | thread | cost | note |
|---|---|---|---|
| C1 | **HLE effort ladder with repeats** — {low, medium, xhigh} x 5q x 3 reps | ~2 h | Answers Mark's "medium is the sweet spot" hypothesis *and* measures run-to-run variance, which we currently have none of. At temp 1.0 repeats are genuine samples, unlike `headlab`'s deterministic replays. The 80 % parse figure is **one draw**. |
| ~~C2~~ | ~~Does VBR ever leave entry tier?~~ **ANSWERED 08-16** — `/slots` read `kv_bpv: 16.0` throughout a tensor-split run. It does not engage at these fills; VBR results are f16 in disguise. | — | `/slots` exposes `kv_bpv`. Receipts show VBR enters at f16 and degrades only under pressure, and in past tests *never engaged* (`kv_bpv: 16.0` throughout). If his sessions never pressure it, his "VBR is sharper" experience may be "VBR is f16". |
| ~~C3~~ | ~~Build a true upstream reference~~ **DONE 08-17** — `~/llama_upstream` on `.73`, `ggml-org/llama.cpp` **`34af94c`**, built sm_60. Confirmed genuine: KV type list has **no turbo types**. **Upstream does NOT collapse.** So the defect is *not* inherited from current upstream — it is fork-side, or upstream fixed it after both forks branched. See `RESULT_UPSTREAM.md`. | — | — |

## New from the upstream result — the highest-value thread now

| # | thread | cost | note |
|---|---|---|---|
| ~~U1~~ | ~~Find the commit~~ **DONE 08-17** — `5fd308947` (cuda : TurboQuant MMVQ/WHT/inner-quant kernels), direct parent clean. buun does **not** have it: the forks hit it independently. See `RESULT_CULPRIT.md`. | — | — |
| ~~U4~~ | ~~Upstream mixed-type under `-sm tensor`~~ **DONE 08-18** — upstream ABORTS identically. buun has no bug; that half of O3 is withdrawn. Tom is the outlier for allowing mixed pairs. | — | **Blocks the buun report.** Upstream refuses `K != V` without `GGML_CUDA_FA_ALL_QUANTS`; Tom's fork added an allow-list. If upstream aborts too, buun has no bug and the report is withdrawn. |
| ~~U5~~ | ~~Fidelity pass~~ **DONE 08-18** — `RESULT_U5_FIDELITY.md`. "Clean" spans 55x in R; turbo2 flips 12.4% of top-1 tokens. Next: same panel on buun's build for turbo8/tcq/VBR. | — | Every "clean" cell in the compatibility map means *not degenerate*, never *faithful*. `hazard-bench/frontier-hazard.cpp` is public-API-only and drops into any tree — audited, 366 lines, no shell-outs or network. Also the instrument for the GQA-gradient question below. |
| U6 | K-sensitivity vs GQA ratio ladder | ~2 h | buun: "K > V is a generalization but not true layer-by-layer." The fleet spans GQA 3:1 (Llama-3.2-3B), 4:1 (Qwen3.5-4B/9B), 6:1 (Qwen3.8-27B) — a K-bits ladder across those tests whether K damage scales with the broadcast factor, which is the mechanism Tom's guard assumes. |
| U7 | Re-test VBR with `layer-pricing` | ~2 h | Our VBR result (`kv_bpv 16.0` throughout) measured the one state where VBR *is* f16. Its value is the per-layer schedule; buun has swept tables for Qwen 27B and a generic fallback order. |
| ~~U1-old~~ | ~~Find the upstream commit that fixes (or never had) it~~ | ~1-2 h | The decisive follow-up. Upstream `34af94c` is clean; both forks collapse. Either upstream fixed it after the forks branched, or the forks introduced it. `git bisect` on `~/llama_upstream` between each fork's merge-base and master, using the 4B `q8_0` arm as the test, **names a specific commit** — which turns the report from "your fork is broken" into "cherry-pick this". Best possible shape for both maintainers. |
| U2 | Are the two forks' copies of `fattn.cu` / `ggml-backend-meta.cpp` identical to each other? | ~15 min | If yes, they share a patchset and the bug came in with it — a much simpler story than two independent regressions. Pure `diff`, no GPU. |
| U3 | What are the forks' merge-bases with upstream? | ~10 min | Bounds the bisect range for U1 and dates each fork's divergence. Pure git. |
| C4 | **empero-ai/Qwen3.8-9B: real distillation gain or extraction artifact?** | ~1 h | Card claims MMLU +26 pp strict-match over Qwen3.5-9B, but the *base* scores 0.251 strict — chance for 4-way MC — while GSM8K (extraction-robust) went **down** 0.015. Our harness reports parse rate separately from accuracy, which is exactly the instrument `lm-evaluation-harness` lacks. Base model already on disk. |

## New from 2026-08-16

| # | thread | cost | note |
|---|---|---|---|
| **N1** | **Is the KV collapse `head_dim`-256-specific?** — **UNBLOCKED, no transfer needed** | ~40 min | Decisive test for the mechanism, and now the *only* live route to it since **N4 turned out unanswerable** (a quantized V cache requires flash attention, so "quantized K+V with FA off" is unreachable). **Correction:** this entry previously named Qwen3.5-9B as the D=128 model to copy — it is **D=256** (`key_length=256`, GQA 4:1), as is every other Qwen here (3.5-4B, 3.6-28B-REAP, 3.8-27B). The real candidate was already on `.73`: `~/AI/Models/tqstudy/Llama-3.2-3B-Instruct-BF16.gguf`, **D=128**, 24 heads / 8 KV (GQA 3:1, below the auto-asym threshold). Staged as `kv_d128.sh` with an L0 gate for BF16-on-sm_60. |
| ~~N2~~ | ~~Does another buun commit reproduce?~~ **DONE 08-18** — three commits, three behaviours. `87c351d28` and `02f8581` ABORT via buun-added guards; only `a8e5b5a38` collapses silently. Ordering unknown (a8e5b5a38 unfetchable). | — | `1abf2d28c` vs `.73`'s `a8e5b5a38`. Free bisect. Blocked on the HumanEval+ ladder. |
| ~~N3~~ | ~~Does Tom's fork reproduce?~~ **DONE 08-17** — `RESULT_XFORK.md`. **Yes, identically.** Both bugs are shared; the abort's trigger set is fork-dependent. Also isolated: the collapse needs K *and* V quantized. | — | — |

## New from 2026-08-17

| # | thread | cost | note |
|---|---|---|---|
| ~~N4~~ | ~~Is the collapse in the flash-attention path?~~ **UNANSWERABLE by flag toggling, 08-17** | — | `-fa off` cannot be combined with the failing config at all: under `-sm tensor` the server refuses (`SPLIT_MODE_TENSOR requires flash_attn`), and under `-sm layer` it refuses again (`quantized V cache requires flash_attn`). **The collapsing configuration only exists with FA enabled**, so toggling FA cannot isolate it. Needs a different instrument — N1, or a build with the fused path forced off. |
| ~~N5~~ | ~~"Both stock" or "both the same stock type"?~~ **ANSWERED 08-17** — neither. Mixed stock types **abort**, symmetrically. Three outcome classes, see `RESULT_XFORK2.md`. | — | — |
| ~~N6~~ | ~~Does the turbo3-symmetric abort need `-sm tensor`?~~ **ANSWERED 08-17** — **yes.** Clean under `-sm layer` (U9). The collapse is split-independent; the abort is not. | — | — |
| ~~N7~~ | ~~Does buun's fork emit the same `/`?~~ **ANSWERED 08-17** — **yes**, 3/3 with bodies captured (U8). Identical failure, not just identical statistics. | — | — |
| N8 | Stock-grid breadth: `q5_1`, `iq4_nl` symmetric | ~10 min | `iq4_nl` **aborts** (U7, legitimate). `q5_1` is **VOID** — U6 hit a port-bind race behind U5's core dump and measured nothing. Both re-run as `kv_fa.sh` F5/F6. |
| N9 | **Re-check any published turbo3 number on a GQA>=6 model** | — | With the guard at default, `-ctk turbo3 -ctv turbo3` measures `q8_0` K + turbo3 V. Any of our own turbo3 receipts on such a model may be mislabelled. Audit, not an experiment. |

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
| O3 | **buun + Tom: stock quantized KV collapse, and the split-axis abort** | **UNBLOCKED, and the audience changed 08-17.** Both bugs reproduce on **both** forks (`RESULT_XFORK.md`), so this goes to both maintainers, not buun alone. Hold until **N4** (`-fa off`) — if that localises it to FA dispatch the report is dramatically sharper, and C3 decides whether it is really an upstream report. Pastable not drafted; Mark authors. |
| O6 | **Tom: the auto-asymmetric guard prevents a crash, not a PPL regression** | New 08-17. His code comment justifies it on fidelity (PPL 2887 vs 7.4); on sm_60 + tensor split, `TURBO_AUTO_ASYMMETRIC=0` **hard-aborts**. Also worth flagging that the guard makes `-ctk turbo3 -ctv turbo3` silently measure `q8_0` K + turbo3 V on GQA>=6 models. Pairs naturally with the #295 pastable already owed him. |
| O4 | **buun: template v3 for Qwen3.8** | 3.6→3.8 rewrite dropped 4 of his 25 fixes (`\| safe`, `loop.previtem`, 9 `raise_exception` sites, `developer` role). Worth telling him; a v3 would have users immediately. |
| O5 | GGML sm_60 issue | filed, **open and unconfirmed** |

## Long-standing / low urgency

| # | thread | note |
|---|---|---|
| L1 | Prompt-cache prefix fix, `apollo_server.ts:449-479` | Diagnosed, never implemented. Predates this campaign. |
| L2 | HLE seed policy — canonical id set vs own-seed | Mark's call. Canonical makes numbers comparable and concentrates leak risk; own-seed is safer and costs the paired power. `build_subset.py --seed N` supports either. |
| L3 | `.194` HumanEval+ ladder | Long-running. Status unchecked in a while. |
| L4 | A judge stronger than Qwen3.5-9B | Current judge validated 5/6 with its miss in the conservative direction, so numbers are floors. A cloud judge would send HLE gold answers to a third party — against the canary and our own hygiene rules. Prefer a larger local model. |
