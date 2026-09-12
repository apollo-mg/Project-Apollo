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
- **9070** is running the einstein chain (`viability/einstein_chain.sh`, started 13:15): the IQ4_XS
  primary, then the IQ2_M secondary, ETA ~15:00. The leftover Swift server was stopped. Ledger timer
  now **hourly** (was every 3 h).

## Unfinished work, highest value first

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
  - **EXL3 inference: the first model RUNS on sm_60 (2026-09-12 13:49).** `turboderp/Qwen3-0.6B-exl3`
    @ 4.0bpw loads in 5 s, answers `Paris`, writes coherent greedy text, decodes at 69.6 t/s. But it
    has no `mul1` codebook, so it exercises only the loader and the reconstruct/cuBLAS path. **The
    real test is `Qwen3.8-27B-exl3` @ 4.00bpw** (`mul1`, int8 path), staged on `.73:/mnt/HDD/exl3/`;
    prereg `PREREG_EXL3_SM60_INFERENCE.md`, driver `exl3_sm60_qual.py`, raw in `exl3_sm60/`. It needs
    the wake proxy paused for ~1 h.
  - **`.73` is suspended by our own wake proxy after 30 min without API requests, even mid-job** —
    pause the proxy or run a WoL watchdog for any long job there (memory: `wake-on-demand-73`).
    Before suspending it runs `pkill -x llama-server` on the node, which kills **any** llama-server
    there, a test server included — so for the EXL3 test the proxy must be paused, not raced.
- **DavidAU einstein termination (donboyle's report)** — `viability/PREREG_EINSTEIN_TERMINATION.md`
  + Amendments 1–3. The pilot reversed the premise: at IQ4_XS the **xhigh control** ran away inside
  `<think>` and einstein did not. Scored run chained by `einstein_chain.sh`: IQ4_XS primary, then the
  IQ2_M secondary. 4 of 36 cells previewed by the pilot (same seed) and must be reported both ways.
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
