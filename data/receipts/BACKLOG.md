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
| ~~B2~~ | ~~Reconcile the parse-rate disagreement~~ **DONE 08-18** — `RESULT_B2_PARSE_RATE.md`. **7/7 disputed parses are `finish_reason == "length"`**; 43 % contain multiple `Exact Answer:` strings, i.e. drafts. `run_hle_mini.py` (content-only) is correct; `rejudge.py` must skip `reasoning` when truncated. Bigger finding: among responses that *finish*, the content parser is **12/12 = 100 %** — the "22.8 % parse rate" is the **79 % truncation rate**, a token-budget problem, not a parsing one. |
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
| S5 | **DFlash2 port + Pascal/RDNA4 evaluation** | ~4 h | `https://inco.ai/blog/dflash2/` (jabbatheduck, 2026-08-18). Adds a **path selector** (bilinear scoring over adjacent token pairs) and **two-tap depthwise convolutions** to fix suffix decay; keeps **top-16 candidates per position**. Claims **2.7-3.4x** on Qwen3.8-27B at batch 1, acceptance length **+16-25%**. **Why this fleet matters:** tested only on **M5 Max, Blackwell and TPUs** — all memory-rich and modern. Our `S2` result already shows DFlash's depth advantage *inverts* on Pascal and that `dfl_n15` **OOMs at 16 GB** because DFlash carries a separate model + context where MTP shares the target's; **top-16 candidates per position can only make that worse**, and no memory requirements are documented. Also: the selector's final walk is **sequential**, and Pascal is where we measured serialization hurting most. Port after TheTom's other project. **Weights on disk 2026-08-20**: `/mnt/TG_2TB/AI/Models/Qwen3.8-27B-DFlash2` (3.6 GiB, safetensors, `DFlash2DraftModel`). Config confirms the blog: `block_size 8`, `conv_kernel_size 2`, `selector_rank 256`, 5 layers, `hidden_size 5120`, GQA 4:1, `sliding_window 2048`, `num_target_layers 64`. Ships for **sglang/vllm only** — there is no llama.cpp path, so it is unusable on this fleet until the port exists. **Note `num_target_layers: 64` against the 27B's 65 blocks** — reconcile before porting. |
| U7 | Re-test VBR with `layer-pricing` — **HALF ANSWERED 08-18** | ~1 h | **`"vbr"` is a CLI alias, not a ggml type** — `common/arg.cpp:342` resolves it to `GGML_TYPE_TURBO3_TCQ`; there is no `GGML_TYPE_VBR`. So the VBR *base* type is already measured: `RESULT_U5B_BUUN.md` turbo3_tcq **R 63.23**, ~2x better than plain turbo3 (125.29). Only the **dynamic per-layer schedule** remains, and it needs `VBR_LAYER_SCHEDULE` (or `--vbr-policy`/`VBR_POLICY_LADDER`) — not `-ctk`. frontier-hazard rejects `-ctk vbr` because its private `type_from_str` walks `ggml_type_name()`, which never returns an alias; that is a tool limit, **not** the non-engagement the old `kv_bpv 16.0` run suggested. |
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

## New from 2026-08-20 — the calibration tier

| # | thread | cost | note |
|---|---|---|---|
| **A1** | **tier_cal MEASUREMENT corpus (~300 paired items)** | ~1 day authoring | `tier_cal` as shipped is a **gate**: 16 items, enough to catch "confabulation blew up", nowhere near enough to detect a *change* between two quants. `tier4/TIER3_INSTRUMENT_SELECTION.md` puts the paired requirement at ~311 items at 15 % disagreement. Until this exists, **no calibration delta may be quoted from the fixture** — and the framing that motivated the tier ("the capability most at risk under quantisation") is a measurement ambition the gate cannot satisfy. Highest risk of being mis-cited of anything in the repo. |
| **A2** | **Verify tier_cal's asserted facts** | ~1 h | Two assertions, both of which *invert* the item if wrong. (a) Answerable golds are from memory, unchecked — a wrong gold penalises a **correct** model. (b) Unanswerable items are *asserted* unanswerable; if `Halverstead`, `Kellsworth`, `Fairmount` or *The Winter Compass* names something real, the item punishes a model for knowing. **Blocks publication**, not the first run — the first run is itself a test of the fixture. |
| **A3** | **First `tier_cal` run against a known-good stack** | ~20 min | Nothing here has been executed. Watch for the two revision triggers: over-abstention >3/8 on a healthy stack means the *answerable* arm is too obscure, not the model too timid; 0/8 confabulation **and** 0/8 over-abstention on a stack we know is damaged means the unanswerable items carry a surface tell and are being pattern-matched. |
| **A4** | **A real judge for the fixture** | ~2 h | The fixture *declared* "judge as backstop" from the day it was written and **one was never implemented** — `run_tier` did exact match only, and `T2-09` (`66 2/3 km`, a correct rendering of 200/3) was failed by the mechanism the fixture said would not be used alone. Dry run 01's unit-tolerant numeric compare covers the numeric cases, so this is no longer urgent, but **any free-text gold will need it** and the A1 corpus may generate some. `L4` applies: prefer a larger local model; a cloud judge is out under the hygiene rules. |
| **A5** | **Cost model for the unanswerable arm** | ~30 min | Dry run 01: `T1-05` truncated at 512, `CAL-U5` at 3067/3072, and both are abstention items. Concluding "no such thing exists" means EXHAUSTING a search; answering terminates on a hit. Measure the token ratio between paired arms before sizing `A1` — at 240 unanswerable items a 3-6x ratio dominates the corpus's runtime, and any per-item timeout would preferentially kill that arm, biasing the headline toward UNDER-reporting confabulation. |

## Substantial experiments

| # | thread | cost | note |
|---|---|---|---|
| S1 | **Full `subset_v1` (200q) at `reasoning_effort=low`** | ~4.6 h | First real HLE number for a local 27B. Was 8.1 h projected at `xhigh` with a 0 % parse rate, so it was never viable before. |
| ~~S2~~ | ~~DFlash on Pascal~~ **DONE 08-18** — `RESULT_S2_DFLASH_PASCAL.md`. **The curve inverts**: DFlash climbs monotonically on RDNA4 (peak 150.66 at n=15) but peaks at n=3 on Pascal; MTP at n=15 is *slower than not speculating* (14.65 vs 28.87). Acceptance matches the 9070 XT within 1 pp at every depth, so it is hardware, not drafting. Power cap never bound (91.7 W busy vs 150 W); the 1063 MHz clock pin is the active constraint. `dfl_n15` OOMs at `-c 8192` — DFlash carries a separate model + context where MTP shares the target's. The entry's "228 W against a 300 W cap" premise was stale (cap is 150 W). |
| S3 | **TCQ throughput-per-fidelity: Pascal vs RDNA4** | ~3 h | `turbo3_tcq` wins on margin (76/120 → 94/120 with depth). But Viterbi decode is sequential — TCQ spends compute to save bits, and Pascal at 150 W is compute-bound. Prediction: the margin win may not survive as a *throughput* win there, while looking excellent on RDNA4. Fleet spans both regimes. |
| S4 | **VBR rate-distortion curve** | ~3 h | VBR has no fixed operating point; point comparisons against static codecs are category errors, and one already produced a wrong conclusion ("VBR beats turbo4 at 100 % fill" — artifact of unequal budget). Right instrument: fidelity vs **achieved `kv_bpv`** across fill levels, matched on achieved bitrate. |
| S6 | **bartowski's Q8_0-body draft-head question** *(renumbered 08-20 — was a second `S5`; DFlash2 keeps `S5`)* | ~1 h | Offer posted, awaiting reply. Our head-isolation used an `IQ3_XXS` body — his "doesn't matter much" regime. His actual uncertainty is about a `Q8_0` body, which we never built. |

## Contributions / outward

| # | thread | status |
|---|---|---|
| O1 | AtomicChat discussion #65 — `AD-IQ3_S` head built with no importance data | **posted, awaiting reply** |
| O2 | bartowski thread — Q8_0 MTP head offer | **posted, awaiting reply** |
| O3 | **buun + Tom: stock quantized KV collapse, and the split-axis abort** | **UNBLOCKED, and the audience changed 08-17.** Both bugs reproduce on **both** forks (`RESULT_XFORK.md`), so this goes to both maintainers, not buun alone. Hold until **N4** (`-fa off`) — if that localises it to FA dispatch the report is dramatically sharper, and C3 decides whether it is really an upstream report. Pastable not drafted; Mark authors. |
| O6 | **Tom: the auto-asymmetric guard prevents a crash, not a PPL regression** | New 08-17. His code comment justifies it on fidelity (PPL 2887 vs 7.4); on sm_60 + tensor split, `TURBO_AUTO_ASYMMETRIC=0` **hard-aborts**. Also worth flagging that the guard makes `-ctk turbo3 -ctv turbo3` silently measure `q8_0` K + turbo3 V on GQA>=6 models. Pairs naturally with the #295 pastable already owed him. |
| O4 | **buun: template v3 for Qwen3.8** | 3.6→3.8 rewrite dropped 4 of his 25 fixes (`\| safe`, `loop.previtem`, 9 `raise_exception` sites, `developer` role). Worth telling him; a v3 would have users immediately. |
| O5 | GGML sm_60 issue | filed, **open and unconfirmed** |
| O7 | **TheTom: review `hermes-go`** | Owed — Mark told Tom he would look at it. `https://github.com/TheTom/hermes-go` (reachable, not cloned). **Do not conflate with `engines/hermes-webui`, which is `nesquena/hermes-webui` and unrelated to Tom** — two "hermes" trees in this workspace is a live footgun for anything sent to him. Standing rule applies: read every third-party file before executing it. |

## Long-standing / low urgency

| # | thread | note |
|---|---|---|
| L1 | Prompt-cache prefix fix, `apollo_server.ts:449-479` | Diagnosed, never implemented. Predates this campaign. |
| L2 | HLE seed policy — canonical id set vs own-seed | Mark's call. Canonical makes numbers comparable and concentrates leak risk; own-seed is safer and costs the paired power. `build_subset.py --seed N` supports either. |
| L3 | `.194` HumanEval+ ladder | Long-running. Status unchecked in a while. |
| L4 | A judge stronger than Qwen3.5-9B | Current judge validated 5/6 with its miss in the conservative direction, so numbers are floors. A cloud judge would send HLE gold answers to a third party — against the canary and our own hygiene rules. Prefer a larger local model. |
