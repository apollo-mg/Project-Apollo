# Findings index — keyed by MECHANISM, not by experiment

**Why this exists.** On 2026-08-16 a day of work re-derived at least six things already sitting
in this directory: that prompt-cache reuse changes temp-0 output, that batch composition changes
it upstream too, that MTP's instability is an MTP x prompt-caching interaction rather than MTP
alone, that MTP's nondeterminism lands differently by content type, that `--reasoning-budget`
had already been characterised, and that running a model at temp 0 outside its recommended
sampling envelope costs wall-clock and serving stability.

None of that was lost. It was **unfindable**, because 168 receipts are named after the
experiment that produced them, and the lookup you actually need is *"has anyone here already
touched this mechanism?"*

`FAILURE_MODES.md` catalogues how we get things wrong. This catalogues what we already know.
Grep this file before designing anything.

**Rule: when a receipt lands, add a line here.** One line, the mechanism tags that would make
someone find it, and the claim in a form that is checkable.

---

## determinism · reproducibility · temp-0

| finding | receipt | date |
|---|---|---|
| Temp-0 nondeterminism has **two independent causes**; concurrent batched decoding is **present upstream**, `-np 1` is the control | `hermesagent20/DETERMINISM_ROOT_CAUSE.md` | 07-27 |
| Prefix-cache reuse changes temp-0 output **on genuine upstream**; `cache_prompt=true` is the DEFAULT, `--no-cache-prompt` required to avoid | `hermesagent20/PREFIX_CACHE_CHANGES_OUTPUT.md` | 07-27 |
| **MTP is deterministic at temp 0.** The instability was MTP x prompt-caching, not MTP | `battle16gb/MTP_CACHEPROMPT_FALSIFICATION.md` | 07-30 |
| MTP nondeterminism lands by content type: **prose drifts, tool calls hold, code breaks** | `battle16gb/MTP_STRUCTURED_OUTPUT.md` | 07-29 |
| Upstream knows the MTP mechanism; MTP tensors load even when never requested | `battle16gb/MTP_UPSTREAM_ROOT_CAUSE.md` | 07-30 |
| f16 control is **bistable within one build** on Polaris — byte comparison at K=1 is invalid there | `battle16gb/F16_CONTROL_BISTABLE.md` | 07-31 |
| Speculative decoding never reproduces non-speculative output — **CONFIRMED 08-18 with `cache_prompt` swept both ways**. MTP's run-to-run instability *was* the caching interaction and is falsified; the off-vs-speculative deviation survives | `spec-decode-determinism/RESULT_SPECULATION_IS_NOT_BIT_EXACT.md` | 08-18 |
| Agent benchmarks on `.73` are not reproducible at K=1 (HA-04 bistable 35/100/100/35) | `battle16gb/HA20_BASE_K3_CONTROL.md` | 07-30 |

## sampling · envelope · reasoning effort

| finding | receipt | date |
|---|---|---|
| **buun `aad850104` fixes the 9070 VBR decode regression and overshoots it.** VBR tg128 at 13k is 28.88 t/s, against 25.26 on `a334fc01e` (+14.3%) and 27.57 on `3823c9eb6` (+4.7%); f16 is within ±0.5%. **The same master does not compile for sm_60 (Pascal).** `allreduce-oneshot.cu` uses three sm_70-only constructs (`__nanosleep`, `ld.acquire`, `st.release`); the runtime refuses that path below Volta, so guards suffice there. The new EXL3 kernels call the unsigned `__dp4a` (sm_61+) and more; a keep-going build is listing the rest | `viability/RESULT_SPEED_AAD85.md` | 09-11 |
| **Pelican three-way at matched IQ3_M.** DavidAU's Twin-Turbo thinks 0.35× as much as base Qwen3.8-27B (p = 0.024, 5 v 5), but its longer answers leave total tokens only ~12% lower (n.s.). This replicates the earlier result, now against a matched base. **Qwopus3.8-Flash in mradermacher's i1 GGUF skipped thinking in 2 of 5 reps:** that template, copied from Jackrong's safetensors repo, never opens `<think>`; Jackrong's own GGUF ships the stock template. One real structural failure in 15 (base r3, a white neck on white). Four scorer artifacts, three of them scenery near the subject | `svgbench-pelican3/RESULT_PELICAN3.md` | 09-11 |
| **DavidAU's three IQ4_XS files are labelled correctly, but the model card overstates the MTP variant.** Plain has no MTP head. MTP adds a 226.5 MB head. MAX-MTP adds a BF16 output (+1.50 GB) and a Q8_0 head (+0.22 GB). The sizes reconcile to the byte. The card's "MTP tensors at Q8_0 for all quants" holds only for MAX: the MTP IQ4_XS head is IQ4_XS/Q5_K, and the IQ3_M's is Q4_K. Plain and MTP were quantized with different imatrix files; the trunk matches except for sparse changes (0.2–1.8% of blocks) in the last ~8 layers. All three are predicted to overflow the 9070 at the ladder's 24k q8_0 (plain by 269 MiB) | `svgbench-davidau/NOTE_IQ4_XS_VARIANTS.md` | 09-11 |
| **DavidAU's Twin-Turbo template drops the model's own tool calls from the history.** Its `{REASON:…}` parser rebuilds every message as `{role, content}`, so the assistant turn that made a call renders empty where stock renders `<tool_call>…`. This matches the HF report (probe says `supports_tool_calls: false`; turns end without a call). A one-line fix (keep untagged messages whole) restores stock's rendering, verified with jinja2 and with llama-server's own probe (`supports_tool_calls` false -> true) | `svgbench-davidau/NOTE_TEMPLATE_TOOL_CALLS.md` | 09-11 |
| **DavidAU's Twin-Turbo Qwen3.8 tune thinks ~1/4.5 as much as stock at `medium` on the pelican, but its answers run ~1.4x longer, so total tokens fall only ~31%** (3,072 vs 4,470 median; p = 0.108, n = 3 vs 10). The pre-registered total-token predictions are falsified; the thinking split is descriptive. Its template's `medium` injects nothing, same as stock | `svgbench-davidau/RESULT_TOKENS.md` | 09-11 |
| **"Consider plausible alternatives" is the clause that runs away** — NO-STOP 2/24 vs 0/24 for "validate key assumptions"; abstention channel underpowered (20 vs 20). Verbosity transfers fully from system block to user turn (208k vs 215k chars); abstention damage only half | `viability/RESULT_CLAUSE_DECOMP.md` | 09-07 |
| **Correcting Spark's sampling drops abstention 18/24 -> 12/24 while the answerable arm does not move at all** (18/24, same items). `top_k` binds only at high-entropy positions -- exactly where abstention is decided. Earlier "abstention is not Qwen-specific" claim WITHDRAWN | `viability/RESULT_SPARK4B_CORRECT_SAMPLING.md` | 09-07 |
| **Good abstention is NOT Qwen-specific** — Spark-X2.5-4B (2.42 GiB, different vendor/arch) scores 18/24 abstained, 18/24 answerable. But its thinner knowledge means abstention and ignorance are not separable here — it abstains on `CAL-U3` where every Qwen config confabulates, and Qwen at IQ2_XS does the same by *losing* the retrieval | `viability/RESULT_SPARK4B_TIERCAL.md` | 09-07 |
| **Deliberation is a search: helps when a target exists, hurts when it doesn't.** Same item + same effort, the reps that CONFABULATED thought **2.5-10.9x longer** than the reps that abstained (3/3 items). Reconciles our ladder with AA's opposite result — their corpus is all-answerable, ours all-unanswerable | `viability/RESULT_SEARCH_ASYMMETRY.md` | 09-07 |
| **Published hallucination figures do not report the effort setting** — AA's 70 % non-hallucination for Qwen3.8-27B is measured at `xhigh`, the model's *worst* of three settings by our matched ladder (confabulation 6/24 vs 3/24 at medium). Third-party context, not our measurement | `viability/NOTE_AA_OMNISCIENCE_LINEAGE.md` | 09-07 |
| **Abstention survives IQ3_XXS and improves** — 23/24 vs Q6_K's 21/24, answerable 24/24 both. `CAL-U3`, deterministic 10/10 on Q6_K, flips to 1/3. **Only matched pair in the corpus** — GLM and Qwen3.6-35B-A3B are different classes and are NOT controls for it | `viability/RESULT_IQ3_GLIMPSE_MEDIUM.md` | 09-07 |
| **`medium` and `low` are identical on calibration; `xhigh` is the outlier** — abstention 21/21/13, NO-STOP 0/0/5. And `CAL-U3` ("which year did Mendeleev win the Nobel") answers **1906 on 9/9 runs at temp 1.0**, all three efforts: effort does not repair a confident false belief | `viability/RESULT_A6_LOW_RUNG.md` | 09-07 |
| **`xhigh` is worse than `medium` on abstention at the model's published sampling** — confabulation 6/24 vs 3/24, NO-STOP **5/24 vs 0/24**, unanswerable output **6.9x** shorter (characters; these runs record no token counts), answerable 24/24 either way. Greedy did not cause NO-STOP; effort does | `viability/RESULT_A6_EFFORT_NOT_SAMPLING.md` | 09-07 |
| Running at temp 0 **outside the model's recommended envelope** cost 18x wall-clock and a hard serving failure | `scrapebench/SAMPLING_ENVELOPE_QWOPUS.md` | 08-01 |
| `--reasoning-budget`: the same flag does **opposite things** on two arms; a bounded budget rescues both | `battle16gb/reasoning_budget_smoke/RESULT_REASONING_BUDGET_SMOKE.md` | 08-08 |
| `reasoning_effort` is a **chat-template variable** defaulting to `xhigh`; `low` took HLE parse 0%->80% at 6.3x fewer tokens | `hle-mini/POWER.md` | 08-16 |
| **Thinking substitutes for precision** — clean 2x2 on Qwen3.8-27B/HumanEval+ (N=164, K=3): quant gap **3.86pp without thinking vs 1.22pp with**; thinking worth +4.47pp at IQ2_M but only +1.83pp at Q6_K. Pre-registered, CONFIRMED | `qwen38-hep-thinking/RESULT_2X2.md` | 08-17 |
| Thinking **compensates for quantisation damage** — gap collapses 25.0pp -> 3.3pp from Q2 to IQ4 | `battle16gb/PUZZLE_LADDER_FA_ON.md` | 07-17 |
| Thinking suppression is an **interaction**: persona x tools, not either alone | `thinking-suppression-2x2/SUMMARY.md` | 07-26 |
| **The "temp 0.6 for coding" advice is 3.6-era and obsolete on 3.8.** 3.6's template has no `reasoning_effort`, so the card offered a *third* sampling set (thinking/coding, temp 0.6) alongside thinking/general (1.0) and instruct (0.7). 3.8 added the effort dial and dropped the coding set. The knob moved from sampling params (visible everywhere) into the chat template (visible nowhere) | verified from `tokenizer_config.json`, both repos | 08-16 |
| Temperature 0 vs 1.0 moved HLE parse rate **not at all** (20% both); `reasoning_effort` moved it 0%->80%. On this task the temp knob is close to irrelevant next to the effort knob | `hle-mini/POWER.md` | 08-16 |
| Unbounded tool-call arguments at Q4 and Q6 alike — a merge defect, not a quant defect | `scrapebench/QWOPUS_RUNAWAY_ROOT.md` | 08-01 |

| **Qwen3.8 template defaults compound**: `reasoning_effort=xhigh`, `preserve_thinking=on`, `cache_prompt=true` — max exploration + growing reasoning tail + reused prefix | `qwen38-template/RESULT_TEMPLATE_AUDIT.md` | 08-16 |
| buun's 25 template fixes did **not** survive the 3.6->3.8 rewrite: `| safe`, `loop.previtem`, 9 `raise_exception` sites, and the `developer` role all still unaddressed | `qwen38-template/RESULT_TEMPLATE_AUDIT.md` | 08-16 |

## speculative decoding · MTP · drafters

| finding | receipt | date |
|---|---|---|
| **MTP costs 1.2-2.1 GB of VRAM and up to 41% of the KV budget, scaling with context** — 262k: 12,346 MiB without vs 14,464 with; KV budget 5,256 -> 3,127. Explains the 262k deploy thrash: without MTP that config has 65% more headroom. A 16 GB full-context claim must state whether speculation is on | `viability/RESULT_MTP_VRAM_COST.md` | 09-08 |
| **MTP is 1.40x at np=1 and 0.44x at np=8** — worse on aggregate AND per-request. Mechanism is **VRAM starvation, not compute contention**: MTP on cut the fitter's KV budget 4449 -> 228 MiB at np=8 while draft acceptance stayed flat (0.49-0.59). Best cell = np=4 + MTP. Every prior MTP figure here was np=1 | `viability/RESULT_MTP_UNDER_LOAD.md` | 09-07 |
| **A 1.7B draft for a 4B target is 0.75x — a 25% LOSS** despite ~50-59% acceptance; the 2.4:1 ratio makes each draft token cost ~40% of a target token. Quantitative case for MTP (1.68x, shares the trunk) over a sibling draft. **Trap:** `--spec-type` defaults to `none`, so `--model-draft` alone silently does nothing | `viability/RESULT_SPARK_SPECDECODE.md` | 09-07 |
| MTP n-max: **dense and MoE have different optima, for different reasons**; dense wins bigger | `pulsar/MTP_DENSE_VS_MOE_NMAX.md` | 08-03 |
| MTP on 2xP100 MoE: 70.5 t/s, and the **n-max ceiling is set by the MMVQ batch table** | `pulsar/MTP_PASCAL_NMAX_MMVQ.md` | 08-03 |
| MTP on Qwen3.8-27B / RDNA4 is **2.05x faster**; two public "slower" reports do not reproduce | `qwen38-mtp/RESULT_RDNA4.md` | 08-14 |
| DFlash (block-diffusion drafter) beats the MTP head 1.34-1.40x; **content split** — DFlash wins code/SQL/JSON, MTP wins prose | `qwen35-drafters/RESULT_MTP_VS_DFLASH.md` | 08-15 |
| MTP draft head is **quantised blind** — no packager's imatrix covers `blk.64` | `qwen38-packagers/RESULT_MTP_HEAD_QUANT.md` | 08-15 |
| KLD-vs-BF16 charts are **structurally blind** to the draft head; it never runs in a normal forward pass | `qwen38-packagers/RESULT_AD_LADDER_HEAD_AUDIT.md` | 08-15 |
| Speculation multiplies throughput **variance ~8x** (off arms 2-7% spread, on arms 40-58%) | `qwen38-splitmode/RESULT_SPLIT_X_MTP.md` | 08-15 |
| **No single best spec setting on RDNA4** — depth AND content both decide: DFlash n=8 wins code (110.08 t/s, 1.77x), MTP n=2 wins prose (85.72). MTP n=8/15 are *slower than no speculation* on prose | `spec-rdna4/RESULT_SPEC_RDNA4_ORNITH.md` | 08-26 |
| DFlash's depth optimum is **model-dependent**: peaks n=8 on Ornith-9B, not the monotonic-to-15 recorded for the 27B. Do not carry a depth constant across models | `spec-rdna4/RESULT_SPEC_RDNA4_ORNITH.md` | 08-26 |
| **buun fork: DFlash silently drafts nothing** (`n_target_layers=0, target_ids=[]`, ~0 MB ring) — costs ~10%, logs no acceptance, reports success. Works on Tom's fork with identical inputs | `spec-rdna4/BUG_BUUN_DFLASH_SILENT_NODRAFT.md` | 08-26 |
| **Dynamic VBR is default-ON in buun's build and bars ALL draft-model speculation** (co-tenancy ledger, `llama-context.cpp:670`). MTP unaffected (embedded head). Workaround: `-ctk f16 -ctv f16` | `spec-rdna4/BUG_BUUN_DFLASH_SILENT_NODRAFT.md` | 08-26 |

## split modes · multi-GPU

| finding | receipt | date |
|---|---|---|
| `-sm tensor` is **1.62x over one P100**; `-sm layer` across two is **inert** (and bit-identical to single) | `qwen38-splitmode/RESULT_P100_SM_TENSOR.md` | 08-14 |
| Split mode and MTP **compose multiplicatively** — 2.433x measured vs 2.432x predicted | `qwen38-splitmode/RESULT_SPLIT_X_MTP.md` | 08-15 |
| `--numa distribute` is worth **+13.6%** warm decode but makes cold first-response ~2x worse | `battle16gb/DS4_REBASELINE_NUMA.md` | 08-02 |
| **`-sm tensor` disables prompt-cache reuse for EVERY KV codec in buun's fork** — f16/q8_0/turbo3/vbr all re-prefill; all four reuse under `-sm layer`. f16 and q8_0 fail **silently**, VBR is the only codec that prints a diagnostic | `vbr-artifact-store/RESULT_TENSOR_SPLIT_BREAKS_ALL_CACHING.md` | 09-07 |
| That cache failure is **fork-specific and a regression**: upstream `34af94c` and Tom `f6124e9` both reuse under `-sm tensor`; buun broke it between **07-26 and 08-25**, a month before his 09-02 upstream sync | `vbr-artifact-store/RESULT_FORK_ISOLATION.md` | 09-07 |
| **FIXED + VERIFIED same day: buun `a56eeef5`** — tensor-split binding 5/5 (was 3/5), cache reuse 4010 tok -> 4 tok, **18.3x wall**. He fixed the Meta-buffer *producer* across 5 files, not the consumer we pointed at | `vbr-artifact-store/RESULT_FIX_VERIFIED_a56eeef5.md` | 09-07 |
| VBR artifact store reports `runtime_pools=2 bindings=0` under `-sm tensor` — pools discover, none bind. Not multi-GPU (2 GPUs bind fine under `-sm layer`); buun's 08-26 `--tensor-split 1,1` workaround no longer helps | `vbr-artifact-store/RESULT_TENSOR_SPLIT_BREAKS_BINDING.md` | 09-07 |
| Cost of the workaround: `-sm layer` restores reuse (4010 tok -> 4) but forfeits 39% of decode on 2xP100 | `vbr-artifact-store/RESULT_CACHE_AB_SPLITMODE.md` | 09-07 |

## KV cache · quantisation fidelity

| finding | receipt | date |
|---|---|---|
| **buun `a334fc01e` stops VBR's post-reset runaways on gfx1201; its parent does not.** Interleaved x3, stock flags, no boot flags: FIX 0 runaways / 33 resets; PARENT `2fd7e523b` 6/22 (2 of 3 runs latched); OLD `3823c9eb6` 4/31. Per reset P = 0.003, per run P = 0.24. A cap-only count read PARENT clean: master decodes ~9% slower, so the 180 s timeout cut runaways off before 4096 | `viability/RESULT_FIX_A334FC01E.md` | 09-11 |
| **Blind pairwise art judging of the svgbench pelicans: Mark's eye leaned 4-bit, just short of the line** (4-bit ahead in 21/24 cross pairings, p = 0.057; 8/8 repeats consistent). A second, hand-rating rater saw no lean (12.5/24, p = 0.96); pooled 18/24, p = 0.26. A third hand-rating rater also saw none (12.5/24; pooled over three, 17/24, p = 0.35); the three agree on only 58-66% of decisive pairs, so it behaves like taste; the rankings barely correlate (rho +0.28). Both raters preferred, blind, all four corrections the ladder receipt singled out. Structurally sound is not the same as a good picture | `svgbench-blind/RESULT_BLIND_ART.md` | 09-11 |
| **VBR KV degenerates after a `vbr reset`; q8_0 and f16 never do.** buun `3823c9eb6`, gfx1201, interleaved A/B/C x3: VBR 3/3 runs affected, q8_0/f16 0/6 (Fisher one-tailed p = 0.0119); 5/5 degenerate generations followed a reset, 5/27 resets went bad | `viability/PREREG_LATCH_INTERLEAVED.md` (SCORING) | 09-10 |
| **Localised to the fused turbo MMA path.** `GGML_TURBO_MMA_FUSED=0` 0/33 resets bad, `TURBO_TCQ_HOTSWAP=1` 0/33, stock 11/60 (P(0 in 66) ~ 1.7e-6). **buun master `d0f82fd41` does NOT fix it on gfx1201** (5/33). HOTSWAP working contradicts its author's expectation; why is unknown | `viability/PREREG_LATCH_INTERLEAVED.md` (localisation) | 09-10 |
| VBR degeneracy is **episodic, not a permanent latch** — a run fails, recovers on the next task, fails again. Every degenerate generation follows a `vbr reset`; most resets are harmless | `viability/RESULT_VBR_RESET_CORRELATION.md` | 09-10 |
| ~~The latch tracks the GPU power cap~~ **superseded** — the 374->330 W change splits the 09-09 ledger 4/5 vs 0/3 (p=0.071, all VBR), but in the interleaved runs power excursions *anti*-correlated with failure (f16 11.9% of seconds > 374 W, clean; VBR 2.9%, failed). Reading: VBR necessary, timing modulates the rate | `viability/RESULT_POWER_CAP_LATCH.md` | 09-10 |
| **FALSIFIED: there is no VBR context ceiling.** Prefix reuse is perfect at 32k-262k (1 cold prefill, 7 reuses, 0 resets) even at ratio 3.12. The 262k agent thrash is a **prompt-shape** problem — the agent showed `0/14,390 tokens reusable`, which means the prefix is altered, not extended | `viability/RESULT_ENTRY_TIER_CEILING_FALSIFIED.md` | 09-08 |
| **Quantisation degrades KNOWLEDGE before CALIBRATION — and calibration improves as it goes.** Controlled AD ladder, one box/binary/packager: IQ2_XS 20/24 answerable + **24/24** abstention; IQ3_XXS 24/24 + 23/24; IQ3_S 24/24 + 21/24. `CAL-U3` dose-response `1906`x10 -> `1907`x3 -> unstable -> gone | `viability/RESULT_AD_QUANT_LADDER.md` | 09-07 |
| **"Clean" spans 55x in decision danger.** First fidelity numbers: `q8_0` R=10.5, turbo4 68.1, `q4_0` 89.5, turbo3 228.4, turbo2 **817.3** (12.4% top-1 flips) — all of which the collapse detector called clean | `kv-fidelity/RESULT_U5_FIDELITY.md` | 08-18 |
| **turbo4 beats `q4_0`** on fidelity at comparable width (R 68.1 vs 89.5); **`q8_0` beats everything** by 6.5x. Asymmetric `q8_0`/turbo4 (45.2) beats symmetric turbo4 (68.1) | `kv-fidelity/RESULT_U5_FIDELITY.md` | 08-18 |
| q8_0 KV is the **gentlest codec measured and depth-invariant** (98.7% same-top at every ctx) | `hermesagent20/KV_KLD_PANEL.md` | 07-28 |
| Perplexity panels **cannot settle generation-path questions** — teacher-forced != decode | `hermesagent20/KV_QUANT_GENERATION_EFFECT.md` | 07-28 |
| `-fa on` costs **more fidelity than BF16->Q8_0**, and perplexity cannot see it | `battle16gb/FA_EQUIVALENCE_SM60.md` | 07-30 |
| TurboQuant weights **lose to k-quants** on fidelity-per-bit | `pulsar/PHASE1_TQ_FIDELITY_RESULTS.md` | 08-04 |
| The quant label is **not a spec** — three publishers' `Q4_K_M` span 2 GB and ~2x KLD | `qwen38-packagers/RESULT_AD_LADDER_HEAD_AUDIT.md` | 08-15 |
| Stock quantized KV collapses to 512 `/` on sm_60 — **requires K AND V both quantized**; either alone is clean. Reproduces on **both** forks, split-independent, both `q8_0` and `q4_0` | `kv-tensor-split/RESULT_XFORK.md` | 08-17 |
| The `SPLIT_AXIS_UNKNOWN` abort is **shared between forks** (Tom :535 / buun :533) with a **fork-dependent trigger** — buun aborts on mixed f16/quantized, Tom on turbo3 symmetric | `kv-tensor-split/RESULT_XFORK.md` | 08-17 |
| Qwen3.8-27B KV is **~68 KiB/token measured, not the ~256 KiB the naive formula gives** — only ~17 of 64 layers appear to hold full-context KV. 16 GB fits ~4x more context than the folklore number | `kv-tensor-split/RESULT_KV_VALIDITY.md` | 08-17 |
| **Check quantized-KV arms for a silent f16 fallback before trusting a clean result** — `/slots` `kv_bpv` where available, VRAM delta where not | `kv-tensor-split/RESULT_KV_VALIDITY.md` | 08-17 |
| **The collapse enters at `5fd308947`** (cuda : TurboQuant MMVQ/WHT/inner-quant kernels) on TheTom's fork — direct parent clean, single-commit isolation. buun does **not** have that commit: the two forks hit it independently | `kv-tensor-split/RESULT_CULPRIT.md` | 08-17 |
| **A bisect that rebuilds needs a fresh build dir per step** — reusing one produced fabricated GOOD verdicts and named a commit touching zero CUDA files as the CUDA culprit. Check a bisect result against mechanism before quoting it | `kv-tensor-split/RESULT_CULPRIT.md` | 08-17 |
| **buun's tensor-split behaviour varies by commit**: `87c351d28` and `02f8581` **abort** on quantized KV via buun-added guards (`:757`, `:753`); only `a8e5b5a38` fails **silently**. His own assertions already catch this | `kv-tensor-split/RESULT_N2_BUUN_COMMITS.md` | 08-18 |
| `q8_0`+turbo4 — the "speed and correctness" pair — **aborts on buun `87c351d28`**. That recommendation is commit-specific, not general | `kv-tensor-split/RESULT_N2_BUUN_COMMITS.md` | 08-18 |
| **The mixed-KV-type abort is UPSTREAM behaviour, not buun's bug** — upstream `e8f19cc0` aborts on `q8_0`+f16 under `-sm tensor` exactly as buun does; Tom's fork is the outlier for *allowing* mixed pairs | `kv-tensor-split/RESULT_OWNERSHIP.md` | 08-18 |
| **`.194` defaults to NCCL for `-sm tensor` and NCCL fails on its P100s**; `.73` had NCCL absent and used the butterfly path. Pin `GGML_CUDA_ALLREDUCE=internal` for any cross-box tensor-split comparison | `kv-tensor-split/RESULT_OWNERSHIP.md` | 08-18 |
| **The two KV bugs have different owners**: the silent collapse is **fork-side** (upstream clean, both forks collapse); the `SPLIT_AXIS_UNKNOWN` abort **reproduces on genuine upstream** `34af94c` at `:537` | `kv-tensor-split/RESULT_OWNERSHIP.md` | 08-17 |
| **Upstream `-sm tensor` + certain quantized KV pairs = immediate hard abort** on multi-GPU (`q8_0`/`q4_0` mixed, `iq4_nl` sym, `q5_1` sym). f16 control clean, so tensor split itself works | `kv-tensor-split/RESULT_OWNERSHIP.md` | 08-17 |
| **Split-independence of the collapse is MODEL-dependent**: the 27B collapses under layer AND tensor; the 4B only under tensor. Match split mode in every cross-binary comparison | `kv-tensor-split/RESULT_OWNERSHIP.md` | 08-17 |
| Upstream **does** support `-sm tensor` (`{none,layer,row,tensor}`) — do not assume otherwise | `kv-tensor-split/RESULT_OWNERSHIP.md` | 08-17 |
| **PR #295's surviving 23-57 VGPR spill costs no measurable decode throughput** on gfx1201 — turbo2/3/4 all +0.4 to +1.0% post-fix at D=128. No sign of the reported 12-31% turbo2 `ncols=1` regression on this arch | `rdna4-vgpr-spill/RESULT_PR295_RUNTIME.md` | 08-17 |
| **K > V sensitivity is an aggregate, not a per-layer law** — buun's VBR layer-pricing sweep finds a middle-late K layer more expendable than an early V layer. GQA broadcast explains the average, not the layer variation | buun, `buun-quality-bench/layer-pricing` | 08-17 |
| **RDNA4 is clean where Pascal collapses** — same fork, same PR, `q8_0`/`q4_0` symmetric at D=256. Matches the `turing_mma_available() \|\| amd_wmma_available()` gate: false on sm_60, true on gfx1201 | `kv-tensor-split/RESULT_RDNA4.md` | 08-17 |
| Full collapse scope: **D=256 + K AND V quantized + no Turing-MMA and no AMD-WMMA hardware**. Pascal/older NVIDIA and pre-RDNA3 AMD, on Qwen3.5/3.6/3.8 | `kv-tensor-split/RESULT_RDNA4.md` | 08-17 |
| GQA is **not** the variable: the 4B collapses at GQA 4:1 while the clean Llama is 3:1 and the collapsing 27B is 6:1 — no separating threshold | `kv-tensor-split/RESULT_D128.md` | 08-17 |
| **The silent collapse is D=256-only** — `q8_0`/`q4_0` symmetric are clean at D=128 (Llama-3.2-3B) and collapse at D=256 (Qwen3.8-27B). The **abort persists at both** head dims. Scope: the Qwen3.5/3.6/3.8 families; D=128 mainstream unaffected | `kv-tensor-split/RESULT_D128.md` | 08-17 |
| The two KV bugs separate on **three orthogonal axes**: collapse is split-independent + head-dim-dependent; abort is split-dependent + head-dim-independent. Both are cross-fork | `kv-tensor-split/RESULT_D128.md` | 08-17 |
| **Every Qwen GGUF on this fleet is D=256** — 3.5-9B, 3.5-4B, 3.6-28B-REAP, 3.8-27B. Do not assume a small Qwen is D=128 | `kv-tensor-split/RESULT_D128.md` | 08-17 |
| **N4 is unanswerable by flag**: the collapsing config only exists with FA on — `-sm tensor` refuses `-fa off`, and `-sm layer` refuses a **quantized V cache** without FA | `kv-tensor-split/RESULT_FA_AND_GRID.md` | 08-17 |
| Stock grid at D=256/sm_60: only `q8_0` and `q4_0` symmetric **collapse**; `q5_1`, `iq4_nl`, turbo3 symmetric and mixed `q8_0`/`q4_0` all **abort** in the split-axis resolver | `kv-tensor-split/RESULT_FA_AND_GRID.md` | 08-17 |
| `TURBO_AUTO_ASYMMETRIC` prevents a **crash**, not a quality loss, on sm_60 + tensor split; and at its default `-ctk turbo3 -ctv turbo3` on a GQA>=6 model silently measures **`q8_0` K + turbo3 V** | `kv-tensor-split/RESULT_XFORK.md` | 08-17 |
| `enable_thinking:false` **is still honored** by the Qwen3.8 template (0/492 vs 492/492 fired) even though the dial moved to `reasoning_effort` | `qwen38-hep-thinking/PREDICTION_Q6K_THINKOFF.md` | 08-17 |
| **A measured per-model degrade order beats the generic cross-model one 3.79x** at matched bytes — and the gain vanishes at both budget extremes, which is the validity check | `layer-pricing/RESULT_MEASURED_ORDER.md` | 08-26 |
| Order files must use a **matched tier ladder** across compared models. A coarse ladder (f16→t8→t2) loses 6x to a fine one (f16→t8→t4); attributing that to architecture is an artifact error | `layer-pricing/RESULT_MEASURED_ORDER.md` | 08-26 |
| **Layer-pricing SNR mechanism: 3 hypotheses falsified** — cell count, KV layer count, quantisation *level*. Only quantized-vs-unquantized survives, on one comparison | `layer-pricing/RESULT_4B_CONTROL.md` | 08-26 |
| **Terminal-layer V rule RETRACTED as general** — holds in `qwen35` hybrids, inverts on dense Llama (`27v` rank 56/56), and is quant-sensitive (`63v` #1→#5 at Q6_K) | `layer-pricing/RESULT_LLAMA_3B.md` | 08-26 |

## hardware-specific

| finding | receipt | date |
|---|---|---|
| **RDNA4 narrow-band crossover is m 2048-4096 — ~8-16x wider than the RDNA3 values (F16 128, BF16 256) it inherits.** No floor (vector wins 96% at m=4); the F16 band is inert at n<=5 because RDNA4's base threshold is already `ne11 <= 5`. Recommended RDNA4 F16/BF16 `[0, 2048]` | `rdna4-kernel-census/RESULT_PR363_NARROW_BAND_RDNA4.md` | 09-10 |
| **On RDNA4 `mmvf` is the SLOW path at m=10240, k=320**, and F16's `ne11 <= 5` threshold keeps it there two rungs longer than BF16, costing 3.2-3.6x | `rdna4-kernel-census/RESULT_RDNA4_NARROW_MATMUL.md` | 09-09 |
| **Flash-Next full quants protect all 5 qwen4exp structural tensor classes (169 each, F32 — even UD-IQ1_S); the shared MTP head has 2 of them at Q8_0** | `qwen4exp/RESULT_STRUCTURAL_TENSOR_AUDIT.md` | 09-07 |
| sm_60 FAST_FP16 carve-out — median KLD 0.0023 -> 0.000001, same-top 96.5 -> 99.9% | `mtp-sm60/SUMMARY.md` | — |
| Pascal `mul_mat_id` guard costs **~50% of all MoE throughput** on sm_60, and sm_60 doesn't reproduce the bug it guards | `pulsar/PASCAL_MMID_GUARD_COST.md` | 08-03 |
| Pascal decode at 150W is **compute-bound, not bandwidth-bound** (24% of HBM2 peak) | `qwen38-splitmode/NOTE_PRECISION_VS_SPECULATION.md` | 08-15 |
| turbo3 V-cache corruption is **Polaris-specific**; root cause wave64 subgroup ballot packing | `battle16gb/TURBO3_241_WAVE64_FIX_CONFIRMED.md` | 07-31 |
| MoE expert cache on 4xP100 **engages and makes it 2.6-3.8x SLOWER** | `rdna4-moe-cache/RESULT_DEEPSEEK_V4_P100.md` | 08-14 |
| RDNA4 VGPR spills too, worse, and not only at head size 256 | `rdna4-vgpr-spill/RESULT_GFX1201.md` | 08-14 |
| **gfx1201 `qwen35` prefill is 2.6-7.7x slower on Tom's fork**; decode and `llama` arch unaffected. MMQ coverage, build config, SSM kernels and FA selection all eliminated | `rdna4-prefill/RESULT_QWEN35_PREFILL_REGRESSION.md` | 09-06 |
| The MMA flash-attention kernel has **no gfx1201 device code** — `default` and `tile` are the same path, so PR #360's override has nothing to switch between | `rdna4-prefill/RESULT_PR360_MMA_NOT_COMPILED.md` | 09-06 |

## instrument validity — read before designing a benchmark

| finding | receipt | date |
|---|---|---|
| **An omitted flag inherits the FORK's default: buun's KV cache defaults to VBR** (`default: vbr (implicit t4 floor)`). A HumanEval+ run launched without `-ctk/-ctv` ran on dynamic VBR against a prereg that said f16. Pass KV flags explicitly; verify the cache type from the server, not the command line | `FAILURE_MODES.md` AFM-38 | 09-11 |
| **svgbench saturated, and its bit-depth 'confirmations' rest on scorer artifacts.** 7/10 Qwen3.8-27B first drawings at the 10-check ceiling. P-L2 CONFIRMED raw, FALSIFIED however the 2 artifact reps are handled; P-L3 flips only if they are counted as drawn (dropped: 5,396 vs 4,778, 4 reps a side). Clean: 2-bit first drawings as sound as 4-bit (6/6 vs 3/4); 0/22 corrections identical to parent; models fixed semantic faults the scorer can't see | `svgbench-ladder/RESULT_LADDER.md` | 09-10 |
| ~~Visual-feedback use depends on the prompt's reference point~~ **causal claim withdrawn same day** — the two arms varied three things, not one; asking for a fault list is at least as plausible a cause | `svgbench-run/RESULT_REFERENCE_POINT.md` | 09-10 |
| ~~Backpressure isolated~~ **RETRACTED** — the positive control (stock flags, inline drain; latched 3/3 before) came back clean 20/20. Sequential single-rep arms were confounded with time, and an unlogged power-cap change split the ledger. **Interleave arms and always run a positive control** | `viability/RESULT_SLASH_DEGENERACY.md` | 09-10 |
| **hermesbench v5 could not finish by construction** — 13 consecutive tasks hit the 960 s wall. Hermes' length-continuation retries double `max_tokens` (to 32,768) and `HERMES_MAX_TOKENS` is inert for `run_agent.py` (absent from every outgoing request). The same task passes when run first on a fresh server: the trigger is server-side state | `viability/RESULT_V5_TIMEOUT_BY_CONSTRUCTION.md` | 09-09 |
| Prompt-cache reuse did **not** suppress the latch onset (6/6 past task #17 in both arms), and the system prompt was never byte-stable — 22 distinct `sys_sha` per arm | `viability/PREREG_CACHE_REUSE_AB.md` (SCORING) | 09-09 |
| **Killing a harness leaves its agent child alive, and it poisons the next run** | `FAILURE_MODES.md` AFM-36 | 09-09 |
| **A component can report the failure it caused itself, and name the wrong subsystem** | `FAILURE_MODES.md` AFM-35 | 09-08 |
| **A grep that matches the wrong field reads as a finding, not an error** | `FAILURE_MODES.md` AFM-34 | 09-08 |
| **Verify the outcome, not the route.** Same upstream rename broke `hermes-bench-tool-call` (name matching, 6 tasks/run graded wrong) and left `stevibe/HermesAgent-20` untouched (artifact/state verification). Artifact grading pins a runtime instead — a different, smaller cost | `FAILURE_MODES.md` AFM-33 | 09-08 |
| **Fixed the hermesbench skew**: one new module + one changed line normalises dispatcher-wrapped and renamed tool calls at the runner's choke point. **6 tasks recovered per run, 0 regressions** across 2 models x 61 tasks. Spark 47->**53**/61, Qwen 44->**50**/60 | `viability/RESULT_HERMESBENCH_FIX.md` | 09-08 |
| **hermes-agent renamed its tools and hid them behind the discovery bridge on 2026-08-29; the bench (last commit 06-23) still checks the old names.** The 35B baseline ran 07-28 against a different tool surface — **no cross-run comparison in this campaign is valid** | `viability/RESULT_HERMESBENCH_VERSION_SKEW.md` | 09-08 |
| **A "deployment" config passed every startup check and scored 7/61** — 262k context requested with only 3,183 MiB KV available; VBR clamped at its floor, **60 cache resets**, 0/14,390 prompt tokens reusable, 20.8 s re-prefill per turn. Size context to available VRAM, not the model's maximum | `viability/RESULT_DEPLOY_CONFIG_THRASH.md` | 09-08 |
| **hermesbench's fixed wall-clock timeout converts decode speed into apparent capability** — 360 s gives a 118 t/s model **42,480** tokens and a 25.8 t/s model **9,290**. Qwen3.8-27B IQ3 generated for the full window on 21 consecutive tasks and was cut off mid-thought. Cross-model scores from this harness are not quotable | `viability/RESULT_HERMESBENCH_WALLCLOCK_BIAS.md` | 09-08 |
| **Three things look identical in a results table: grader blind spot, different-valid-route, genuine failure — only the trace separates them.** Each stays hidden because the reference model matches the author's assumptions; the first model that differs looks broken | `FAILURE_MODES.md` AFM-32 | 09-07 |
| **hermesbench cannot see tool calls routed through Hermes' own `tool_call` dispatcher** — confirmed on **two models, two vendors** (Spark-4B and Qwen3.8-27B); only the 35B baseline calls directly, which is why it never surfaced. 7 of Spark's 14 non-passes were graded wrong, incl. "expected >=2 todo calls, got 0" when it made 2 | `viability/RESULT_HERMESBENCH_DISPATCHER_BLINDSPOT.md` | 09-08 |
| **A 2.42 GiB 4B drives Hermes Agent: 47/61** (35B-A3B baseline 55-57/61), 29 tool schemas, ~13k-token turns. **Every failure is stateful** — process_mgmt 3/3, todo_plan 3/3, memory_facts 2/2 all fail while neighbours pass; 2 infra errors are 23k-32k token runaways | `viability/RESULT_SPARK4B_HERMES.md` | 09-07 |
| **A 2.42 GiB 4B scores 24/24 on parallel tool calls, chained state and 4 adversarial cases** — incl. NOT calling when a returned value fails the condition, and asking for a missing argument instead of inventing one. But tool-call mechanics != agentic competence: a 27B scores 0/5 process on a real diagnostic task | `viability/RESULT_SPARK4B_TOOLS.md` | 09-07 |
| **`tier_struct` gave contradictory instructions for three dry runs** — `run_struct` never passed `prompt=`, so "reply with ONLY JSON" met "end with exactly one line: Exact Answer". Qwen passed anyway and hid it; a literal-minded 4B scored 2/6 VOID, then **18/18** once fixed | `FAILURE_MODES.md` AFM-31, `viability/RESULT_SPARK4B_STRUCT.md` | 09-07 |
| **"Same vendor" is not a comparison class** — GLM (MoE, prune+quant), Qwen3.6-35B-A3B (3B active, prune) and Qwen3.8-27B (dense, quant) share nothing that makes one a control for another; 3B-active confounds "knows less" with "cannot represent uncertainty" | `FAILURE_MODES.md` AFM-30 | 09-07 |
| **Never reason from a `cut`-truncated diagnostic line** — a field ending in `=` is indistinguishable from an empty value; this shipped a wrong subsystem attribution to a maintainer | `FAILURE_MODES.md` AFM-29 | 09-07 |
| **All four cells 8/8. The instrument saturated.** Zero discriminating power | `qwen38-lowbit/RESULT_2x2.md` | 08-14 |
| Prompt-cache test was **underpowered for the question it asked** | `battle16gb/DS4_PROMPTCACHE_INCONCLUSIVE.md` | 08-01 |
| A published decode rate was a **cold-cache artifact** — warm steady state 2.2x higher | `battle16gb/DS4_DECODE_WARMUP.md` | 08-02 |
| Both headline findings were **a stale wheel**, and that is the finding | `rdna4-gemm-dtype/RESULT_GEMM_DTYPE.md` | 08-09 |
| HLE quant-delta use **withdrawn** — McNemar needs ~10 discordant pairs; a 5% base rate yields 1-6 | `hle-mini/POWER.md` | 08-15 |
| Head-isolation acceptance result recorded **UNRESOLVED** — within-arm swing 5.4pp vs 1.86pp effect | `qwen38-packagers/RESULT_AD_LADDER_HEAD_AUDIT.md` | 08-15 |
| **Argus corpus has almost no discriminating power**: 4 of 6 scenarios saturate, `ambiguous-dave` is failed by every model tested (3 clean / 39 runs, 4 models). Only 1 scenario carries variance | `../../argus/FINDINGS_2026-08-25.md` | 08-26 |
| ~~An n=5 sweep (Cold-Fusion 5/5) dissolved to 10/12, p=0.54 at n=12~~ **RETRACTED 08-27** — all four arms ran against a calendar with no events on the run date; "clean" was unearned. Re-run live: stock 0/12, Cold-Fusion 1/11 valid — no separation, both fail. Envelope: ONE afternoon event on one date | `../../argus/FINDINGS_2026-08-25.md` | 08-26 |
| **No agent arm asks before destroying anything.** stock 0/12, Cold-Fusion 1/11, Carnice 1/11 on a live scenario; the 25-vs-83% spread was the date. Corpus calibration: only **4 of 16** scenarios discriminate, split by scenario class not model | `argus/RESULT_AGENT_ARMS_CORRECTED.md` | 08-27 |
| **`qwen4exp` couldn't use tensor parallelism — because it was missing from a switch, not because the math was missing.** The Qwen-GDN branch already had the right arithmetic; a deny-list default (`llm_arch_supports_sm_tensor`) let qwen4exp past the gate it should have failed. Corrected diagnosis + the 2-line fix | `qwen4exp/RESULT_TENSOR_SPLIT_BLOCKED.md` | 08-28 |
| **`c232282aa` verified on 4x P100** — qwen4exp Meta row passes (NMSE 4.40e-14); every `-ngl 44` compute-buffer mismatch gone; Q2 all-layer smoke passes. But `-sm tensor` is **silently wrong at >=3 devices** (garbage out, no assert) while correct at 2 — same threshold as a pre-existing qwen3next Meta abort | `qwen4exp/RESULT_c232282aa_VERIFY.md` | 08-28 |
| Predictions logged before the tensor-split runs, scored honestly after (P2 and P6 falsified) | `qwen4exp/PREDICTIONS_tensor_split_patch.md` | 08-28 |
| **A long-lived llama-server silently loses ~100x throughput.** 48.3s for a 24-token reply after 14h uptime; 0.3-0.7s after an identical relaunch. Restart before a benchmark leg and record uptime | `FAILURE_MODES.md` (AFM-26) | 08-28 |
| **A time-relative scenario is only a test on the day its fixture is anchored to.** Hardcoded seed dates silently make destructive scenarios unsatisfiable — the agent scores clean because it *cannot* act | `FAILURE_MODES.md` | 08-27 |
| **Non-termination is a SAMPLING claim until proven otherwise** — check the vendor profile for the WORKLOAD (cards publish several), pin `min_p`, read `/props` not the launch command | `FAILURE_MODES.md` | 08-27 |
| Ornith-1.5-9B loops at the card's *coding* profile (temp 0.6 / presence 0.0); agentic work needs the *general* profile (temp 1.0 / presence 1.5). Our n=12 Ornith arm is suspect | `FAILURE_MODES.md` | 08-27 |

## which binary produced this

Three forks are in use and they are **not interchangeable**. Every receipt should name one.

| node | fork | note |
|---|---|---|
| `.73` | `spiritbuun/buun-llama-cpp` (`~/buun_vbr`) | `a8e5b5a38`, **805 commits ahead** of upstream b9637 |
| `.73` | `TheTom/llama-cpp-turboquant` (`~/llama-cpp-turboquant`) | **`f6124e9`** = the #295 merge commit, `version: 205`, built sm_60 08-17 |
| control plane | `giveen/llama-cpp-turboquant` (`moe-cache-test`) | `bb3c3fa` |
| `.194` | `giveen/llama-cpp-turboquant` (`~/moe-cache-cuda`) | `bb3c3fa`, detached on `giveen/moe-cache`. Has buun + origin remotes too — check the *branch*, not the remote list |
| `.73` `llama_stock_ref` | **NOT stock** — carries laguna patches | `adeff9b82` |

There is currently **no true upstream reference binary on either box**, so "does this reproduce
on stock llama.cpp" cannot be answered without building one. `DETERMINISM_ROOT_CAUSE.md` did
test genuine upstream `0e4a03622` on 2026-07-27; that checkout may still exist.
