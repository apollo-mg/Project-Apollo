# Open threads — as of 2026-09-12 (updated midday)

Written to survive a context compaction. **Things we committed to and have not finished**, plus the
facts that were expensive to establish and would be expensive to re-derive. Update or delete lines
as they close; this is a working file, not a receipt.

## Fleet state

- **`.194` is POWERED OFF** (05:59 shutdown after the three-way + Q6_K runs). Everything was copied
  off and verified by sha256 first. Cold boot is ~216 s; BMC at 10.0.0.195 via `tools/s194.sh`.
- **`.73`** rebooted onto NVIDIA 580.178.04; **34 NVIDIA/CUDA packages held** so unattended-upgrades
  cannot desync the driver again. **Our own wake proxy suspends it after 30 min without an
  API request, even mid-job** — all five suspends on 09-12 were proxy-initiated (I first blamed KDE
  input-idle; wrong) — and it stops its llama-server before suspending. The sm_60 qualification worktree and binaries are at
  `~/buun-sm60-qual/`.
- **9070** is free; the einstein chain finished (`cee3750`). A ROCm build of buun `9ae8f0f40`, the same
  commit as `.73`'s qualification build, is at `/mnt/TG_2TB/Projects/buun-9ae8f/build_rocm`. It was built
  15:19 (server target only) and is the first local ROCm binary that contains any EXL3 code.
- **The ledger timer runs hourly at :05** (it was every 3 h) and calls the daily driver through the
  proxy, so a paused proxy costs that hour's ledger run.

## Unfinished work, highest value first

**EXL3 campaign — ACTIVE** (`exl3-campaign/CAMPAIGN_EXL3.md`, opened in `7277557`).
- **Method:** an objection ledger. Default to EXL3 on the P100 nodes and test each reason not to.
- **Scope is P100-only:** all of `exl3.cu` is compiled out under HIP.
- **Test 1 (drop-in): DONE** (`RESULT_EXL3_DROPIN.md`), 7 confirmed and 3 falsified.
  - EXL3 works with the daily driver's exact flags: MTP, vision, VBR at 262k.
  - It decodes at **0.646×** the daily driver as served.
  - **MTP buys EXL3 1.24× against GGUF's 1.69×, at identical acceptance.** The loss is in verification;
    a `--draft-max` sweep would tell whether it is fixable in buun's kernel.
  - Loads take 322 s off `/mnt/HDD` (O10: blocked on NVMe space).
- **Test 2 (RDNA4): DONE** (`RESULT_EXL3_HIP.md`). EXL3 loads, but every EXL3 matmul runs on the CPU;
  `-ngl 99` is slower than `-ngl 0`. Mark offered buun RDNA4 testing.
- **Test 3 (KLD): DONE** (`RESULT_EXL3_KLD.md`, `aa42fe1`), 4 of 5 predictions confirmed.
  - **At matched VRAM, EXL3 is 24% closer to a Q8_0 reference than UD-IQ4_XS** (0.012002 vs 0.015727) at
    32 MiB less VRAM. A GGUF needs ~790 MiB more to match its fidelity.
  - **Perplexity is retired as a fidelity metric here:** it scores Q6_K and Q4_K_M *better than the Q8_0
    they approximate*, and ranks EXL3 last where KLD ranks it second.
  - The gate reproduced the reference bit-for-bit (KLD 0.000000, same-top 100%).
  - **The 5 GB reference stays on `.73:/mnt/HDD/kld/ref.kld`** — any further arm scores against it.
- **Amendment 2 (EXL3 5.00bpw): DONE**, and it corrected the conclusion. **Matched by bitrate, EXL3's
  curve is below GGUF's at both comparable sizes:** 24% at ~13.5 GB, and 28% at Q4_K_M's own 15,448 MiB
  (interpolated 0.005668 vs 0.007840). **The advantage widens with fidelity** — a GGUF needs ~790 MiB
  more VRAM to match EXL3 at KLD 0.012 but ~2.9 GB more at 0.004. EXL3 5.00bpw is within 1.4× of the
  daily driver's fidelity on **4.9 GB less VRAM**. Mark caught the false choice that produced the earlier
  "GGUF wins at +2 GB" reading.
- **"61% of the bits" was the nominal figure.** VRAM is 64% and disk 74% (fixed in `cc0c9a6`).
- **Test 4 (MTP micro-batch sweep): DONE** (`RESULT_EXL3_MTP_SWEEP.md`), all five predictions confirmed
  on the re-run. **A 4-row verify costs EXL3's int8 GEMV 2.08× a single row where GGUF's MMVQ pays
  1.37×** (A(4) 1.92 vs 2.92), which predicts test 1's MTP asymmetry to within a few points. **So most of
  the speed gap is a kernel property buun could address**, not the format. Attempt 1 said the opposite
  purely from a cold first test after a 318 s load; its control caught it, and it is kept in
  `mtp/attempt1_cold/`.
- **Test 6 (MTP depth curve): DONE, gate failed** (`RESULT_EXL3_DEPTH.md`). **Per-request
  `speculative.n_max` is ignored under `--spec-type draft-mtp`** — every depth drafted 7 per step, the
  CLI value — so the curve is unmeasured and P-S1..P-S4 are VOID. The source says the request field
  should reach MTP, which makes it a question for buun. **The accidental depth-7 point is usable:** MTP
  becomes a **net loss** for EXL3 (0.78× of no speculation) while Q6_K still gains (1.10×), with
  acceptance halved to 0.325.
- **Three orchestration bugs cost time, not data** (`6300b36`, `c6d259e`, `d75e2ee`, `e39a08c`; memory:
  `orchestration-chaining-lessons`). A pidfile's absence was read as success; the pidfile registry was
  hardcoded and missed a new runner, so two runs collided and one OOM'd; and the free-node gate
  deadlocked on the daily driver it stops itself. Every result was either clean or voided by its own gate.
- **A HIP port of EXL3 looks tractable** (`NOTE_EXL3_HIP_PORT.md`, source reading). Every Ampere-only
  construct in the int8 GEMV is guarded on `__CUDA_ARCH__`, which HIP does not define, so `cp.async` and
  `dp4a` already fall back to portable C — **the sm_60 path buun wrote for our P100s is the HIP path.**
  What blocks a compile: three unguarded PTX idioms in `exl3-dq.cuh`, the Ampere `mma` GEMV needing
  exclusion, and the two HIP gates. RDNA3/4 can use `__builtin_amdgcn_sudot4` with the first sign flag
  false. **Mark's 9070 is the only RDNA4 in the collaboration and the build tree is standing.**
- **O8 (can we make our own quants?): source reading only, no blocker found**
  (`NOTE_EXL3_QUANTIZER_ON_SM60.md`). exllamav3 sets no architecture gate, and the sampled kernels use
  `half2` intrinsics that Pascal has natively. **3 of 113 CUDA sources were read**, so it is not an
  answer. The decisive test is named and costs about an hour: convert Qwen3-0.6B on `.73` and compare
  its perplexity against turboderp's own 0.6B (20.2864).

1. ~~**Write the Q6_K injection receipt.**~~ **DONE 2026-09-12 (`6831591`)** —
   `RESULT_OVERTHINK_INJECTION_Q6K.md`. The 03:51 quick score ("P-Q5 favoured") is **withdrawn**: it
   credited the injection with the cap's work. B vs C differ in outcome on **0 of 24 cells**. Root
   cause found — the budget message is the *last* thing in the reasoning stream, so it can only
   influence the final answer, never deliberation. **P-Q4/P-Q5 are unresolved and this design cannot
   resolve them.**
2. ~~**Score the three-way HumanEval+.**~~ **DONE 2026-09-12 (`13d3728`)** —
   `nex-mini-ab/RESULT_THREE_WAY.md`. 2 confirmed, 5 falsified. Stock Qwen3.6-35B-A3B 94.11% beat
   both finetunes (ORNITH 90.65%, NEX 89.84/86.99%) while spending 8.6× the tokens.
3. **Base `IQ3_XXS` control for Swift.** `RESULT_SWIFT_BREVITY_TAX.md` compares bartowski Swift
   `IQ3_XXS` against mradermacher base `i1-IQ3_M` — tune *and* quant *and* packager all move. The
   −26% / +20% allocation asymmetry cannot be attributed to brevity training until this runs.
   **Runs on the 9070; no `.194` needed.** Highest-value item that needs no hardware wake.
4. **Re-open the think block, or the injection idea is dead.** The message currently arrives after
   thinking closes. A real test needs a mid-stream turn that re-opens `<think>`, or a budget that
   pauses instead of terminating — an engine-side change. Until then arm C is arm B with extra text.
5. **A harder unanswerable corpus.** CAL is too easy at both bit depths (arm A fails 4/24 at IQ3_M,
   5/24 at Q6_K, and 3 of the 5 are one repeated confabulation in cells no arm can influence).
   **ADVISOR was never emitted as an answer in 288 generations.**
6. **`IQ3_M` on `.194` under the Q6_K server config** — still worth running as a *bit-depth*
   measurement (node, KV type and split currently move with bit depth), but it is **no longer the
   thing that settles the bet**. Demoted from #4.

## Outward-facing, waiting on others

- **DavidAU / `toolcall2.jinja`** — reported a release blocker (crashes when `tool_calls.arguments`
  is a JSON string; guard lost in the merge). Patched file and report are pushed. He asked us to
  test *before* re-GGUFing; awaiting his fix. **Untested by us: whether llama.cpp's minja parser
  behaves the same as Python jinja2 here** — the authoritative check is loading it in llama-server.
- **saifvj's premature-turn-end** — his medium/low/xhigh test supports the "injected instruction,
  not thinking on/off" hypothesis but changed three variables at once (different quant file,
  different starting file state, MTP on). A controlled version is ~30 min: one model, one restored
  starting state, three efforts.
- **buun's EXL3 / sm_60 fix — QUALIFIED on real P100s 2026-09-12**
  (`kv-tensor-split/RESULT_SM60_EXL3_QUALIFICATION.md`). `4d90517b1` + our 2-line e8m0 guard builds
  all of `ggml-cuda` for sm_60, and his `test-exl3-byte-dot` **PASSES on hardware** (exit 0, checked
  against its `SKIP_RETURN_CODE 77`). Worktree + binaries at `.73:~/buun-sm60-qual/`.
  - **New bug for him:** unguarded, `humming-fp8.cu` fails on `__nv_fp8_e8m0`, a CUDA **12.8** type.
    That breaks `ggml-cuda` on **any arch** below 12.8, not just Pascal
    (`NOTE_HUMMING_FP8_NEEDS_CUDA_128.md`, `PATCH_e8m0_cuda128_guard.diff`). **Mark has not told him
    yet**; a draft is pending.
  - **His commit fixed all four objects that broke us at `aad850104`** (exl3 + int8-channel on
    `__dp4a`, both humming FP8 objects on the cc≥7.0 barrier `#error`) — verified from that build's
    `-k` log. Guarding the barrier **unmasked a fifth, latent failure** (e8m0: 0 mentions in the old
    logs, 17 today). I briefly "corrected" this entry to say he fixed only three; that correction was
    itself wrong, and `75c5dfc`'s commit message carries the same error.
  - **Our `LOCAL_PATCH_sm60_guards.diff` is superseded** — do not re-apply it.
  - **EXL3 inference on sm_60 — DONE 2026-09-12** (`kv-tensor-split/RESULT_EXL3_SM60_INFERENCE.md`).
    turboderp Qwen3.8-27B-exl3 @ 4.00bpw: perplexity **+0.55%** against the daily driver's Q6_K at 64%
    of its VRAM (61% of nominal bits per weight, 74% of disk); decode 6.96 / 11.26 t/s (layer / tensor) = 0.89× / 0.85× Q6_K; the int8 path is 2.9×
    faster than reconstruct+cuBLAS. 7 confirmed, 2 falsified. **buun's final-results message is a
    draft with Mark.** Models staged on `.73:/mnt/HDD/exl3/`. **This continues as the EXL3 campaign
    at the top of "Unfinished work".**
  - **`.73` is suspended by our own wake proxy after 30 min without API requests, even mid-job** —
    pause the proxy or run a WoL watchdog for any long job there (memory: `wake-on-demand-73`).
    Before suspending it runs `pkill -x llama-server` on the node, which kills **any** llama-server
    there, a test server included — so for the EXL3 test the proxy must be paused, not raced.
- **DavidAU einstein termination (donboyle's report) — DONE 2026-09-12 (`cee3750`)**,
  `viability/RESULT_EINSTEIN_TERMINATION.md`. Across two models (base IQ4_XS, DavidAU 735-882
  IQ2_M): **xhigh ran away 5/24, einstein 0/24**, every runaway inside `<think>`. On base weights the
  runaway is `E-C1` on every seed, re-litigating a return-type annotation 4, 5 and 13 times. **A
  reply draft for donboyle is with Mark**; it asks the question that decides his fix (a post-answer
  agent loop, or one long think block).
- **buun: Qwen3.8-Flash-Next on Pascal (asked 2026-09-12 ~13:50).** He has improved tensor sharding
  for it and suggests putting the n-gram table on SSD. `.194` (4×16 GB VRAM, 64 GB DDR4, SATA SSD)
  is the box. Our memory says upstream disabled `-sm tensor` for qwen4exp/Flash-Next (#27941) —
  check whether his fork re-enables it first. Related: Jas and Mark's four Flash-Next fixes on Tom's
  fork (TheTom/llama-cpp-turboquant PR #362).
- **Tom / FA f16 pool ratchet on Pascal** — source analysis published
  (`kv-tensor-split/NOTE_FA_F16_POOL_RATCHET_PASCAL.md`); **no measurement taken**. Needs `.194`.

## Offered, not started

- **Streaming safety pass** before the first live stream: scrubbed shell profile, known-safe panes,
  a pre-flight checklist. `~/.ipmi_194`, node IPs, ssh targets and hostnames are all currently
  visible in normal terminal work.
- **Ledger open-loops extractor** — the ledger records what happened but not what was promised.
  This file is the manual version of that feature.
- **Repo re-fronting** (decided in principle, not executed): do **not** rename; rewrite the README
  front matter to describe the lab that exists, move the Sovereign-AI-OS architecture to
  `ARCHITECTURE.md` as history. Repo is ~97% research artifacts by file count; `modules/` has had
  **0** commits in 30 days, `deploy/` untouched since 2026-06-01.
- ~~**Einstein-mode behavioural test**~~ — **now running** as `PREREG_EINSTEIN_TERMINATION.md`; see
  the outward-facing entry above.

## Facts that cost real time to establish

- **The 11/24 CAL baseline ran at `-c 8192`** (escalated retry 7,168); tonight's runs used 16,384
  (retry 12,288). ~5 of its 11 failures are a context artefact. **P-Q1 is withdrawn.** Any
  comparison against `card_xhigh_rep*` must match `-c 8192`. See
  `viability/NOTE_CAL_BASELINE_NOT_COMPARABLE.md`; `tools/compare_runs.py` now enforces this.
- **`reasoning_effort=medium` injects NOTHING.** low +138 chars, xhigh +209, einstein +1,082,
  spoon +3,989. This is why saifvj's medium run failed where BebopVox's low run worked.
- **`--reasoning-budget 0` does NOT stop this template thinking.** Use
  `--chat-template-kwargs '{"enable_thinking":false}'`; verify via `/apply-template` (prompt should
  end `<think>\n\n</think>`).
- **`reasoning_budget_tokens` and `reasoning_budget_message` are settable per request**
  (`tools/server/server-schema.cpp:383,415`), so arms interleave on one server.
- **A fixed seed makes A/B/C arms byte-identical until the cap binds** — the IQ3_M injection run had
  only 3 of 24 cells that could differ. Check this before trusting any arm contrast.
- **`/health` returns 200 before the model is loaded.** Readiness must be a real completion.
- **The vision preprocessor letterboxes non-square images** and the model narrates the black bars;
  pad to square on white.
- **A 3-bit judge missed the only defect verifiable from source** (`BASE r3`, a white neck on white);
  Q6_K caught it. Grade at Q6_K on `.73`, which already serves it with the mmproj.
- **`len(reasoning)` counts an injected budget message as model thinking.** The server delivers
  `reasoning_budget_message` *into* the reasoning stream, as its last content. Subtract it before
  comparing thinking volume across arms, and never substring-search reasoning for a token the
  injected message itself contains (an ADVISOR search reported 18 emissions against 0 real ones).
  `tools/score_overthink.py` does both correctly.
- **Paired per-problem tests beat differencing two pooled rates, and the three-way proves it:** the
  known-null pair (same weights, different socket) showed a 2.85-point pooled "difference" — within
  1.5 points of every real cross-model gap — but returned not-significant on the registered sign
  test, while the real pairs came back p = 0.0023 and p = 0.0079.

## Standing constraints that must not be lost

Public prose is Mark's — Claude drafts, Mark posts. Outward-facing actions (push, PR, post) need
explicit approval each time. Never `pkill -f`/`pgrep -f` a pattern you may be inside. Never remove
the APT hold on `.73` or `.194`. No cloud LLM APIs without authorisation. Credentials never enter
the repo. Verify every model file against its published sha256 before use — a double-writer
corrupted a 12 GB download tonight and only the hash caught it.
