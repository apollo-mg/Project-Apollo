# Open threads — as of 2026-09-12 ~05:00

Written to survive a context compaction. **Things we committed to and have not finished**, plus the
facts that were expensive to establish and would be expensive to re-derive. Update or delete lines
as they close; this is a working file, not a receipt.

## Fleet state

- **`.194` is POWERED OFF** (05:59 shutdown after the three-way + Q6_K runs). Everything was copied
  off and verified by sha256 first. Cold boot is ~216 s; BMC at 10.0.0.195 via `tools/s194.sh`.
- **`.73`** rebooted onto NVIDIA 580.178.04; **34 NVIDIA/CUDA packages held** so unattended-upgrades
  cannot desync the driver again. Daily driver verified serving after reboot.
- **9070** free. Ledger timer now **hourly** (was every 3 h).

## Unfinished work, highest value first

1. **Write the Q6_K injection receipt.** Data is complete and scored
   (`data/receipts/viability/overthink_q6k/score_output.txt`), receipt is NOT written.
   Headline: A 5/24, B 3/24, C 3/24 on the unanswerable arm; answerable 24/24 in all three arms;
   NO-STOP 2 → 0. **P-Q5 (Mark) favoured over P-Q4 (Claude)** — the injection reduced failures by 2
   at Q6_K and by −1 at IQ3_M — but C did **not** beat B, so what is demonstrated is the *cap*, not
   the *message*. Fisher p = 0.70; four events total. Must carry the confound list below.
2. **Score the three-way HumanEval+** against P-T1…P-T7 in `nex-mini-ab/PREREG_THREE_WAY.md`.
   Data retrieved and verified in `data/receipts/nex-mini-ab/` — 4 result files (24 entries each),
   109 failure traces, all logs, the driver scripts. P-T2 is scored both directly and through NEX;
   P-T6 on the v2 run only.
3. **Base `IQ3_XXS` control for Swift.** `RESULT_SWIFT_BREVITY_TAX.md` compares bartowski Swift
   `IQ3_XXS` against mradermacher base `i1-IQ3_M` — tune *and* quant *and* packager all move. The
   −26% / +20% allocation asymmetry cannot be attributed to brevity training until this runs.
4. **`IQ3_M` on `.194` under the Q6_K server config** to settle P-Q4/P-Q5 cleanly. Tonight's two
   runs differ in node, KV type (`q8_0` vs `f16`) and split (none vs tensor) as well as bit depth.
5. **A harder unanswerable corpus.** CAL is too easy at 3-bit (arm A fails 4/24), so both injection
   designs were underpowered. **ADVISOR was never emitted in 48 generations** — nothing was hard
   enough to warrant escalation, so P-O7/P-O8 remain unscoreable.

## Outward-facing, waiting on others

- **DavidAU / `toolcall2.jinja`** — reported a release blocker (crashes when `tool_calls.arguments`
  is a JSON string; guard lost in the merge). Patched file and report are pushed. He asked us to
  test *before* re-GGUFing; awaiting his fix. **Untested by us: whether llama.cpp's minja parser
  behaves the same as Python jinja2 here** — the authoritative check is loading it in llama-server.
- **saifvj's premature-turn-end** — his medium/low/xhigh test supports the "injected instruction,
  not thinking on/off" hypothesis but changed three variables at once (different quant file,
  different starting file state, MTP on). A controlled version is ~30 min: one model, one restored
  starting state, three efforts.
- **buun's EXL3 fix** — not pushed as of 01:00. Until it lands, `.73` cannot build current master
  for sm_60. Our guards for `allreduce-oneshot.cu` live only in `~/buun-aad85` on `.73`
  (`LOCAL_PATCH_sm60_guards.diff`), not upstreamed.
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
- **Einstein-mode behavioural test** — does `{REASON:einstein}` actually produce the ≥5000-token
  "20 agents" brainstorm the card claims? Template-side it injects +1,082 chars. Never run.

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

## Standing constraints that must not be lost

Public prose is Mark's — Claude drafts, Mark posts. Outward-facing actions (push, PR, post) need
explicit approval each time. Never `pkill -f`/`pgrep -f` a pattern you may be inside. Never remove
the APT hold on `.73` or `.194`. No cloud LLM APIs without authorisation. Credentials never enter
the repo. Verify every model file against its published sha256 before use — a double-writer
corrupted a 12 GB download tonight and only the hash caught it.
