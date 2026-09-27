# buun `1c5e564b` on .73: media now survives `--resume` (an image conversation is warm after a restart), the displaced `-np 4` slot is restored from host in 0.33 s, the resume save is 2.3x faster, and every `0b2789f23` fix still holds. The split-state stack overflow is untouched in source

**2026-09-27 12:17-12:33, `.73`** (2x P100, `-sm tensor`). Build `/mnt/HDD/buun-1c5e5/build_sm60` (`1c5e564b`
"server: support media in resume and VBR host cache", 5 commits on top of `0b2789f23`: `cd51a86b`, `bad517d6`,
`303392c1`, `cd751876`, `1c5e564b`).

**Setup:**
- Daily VBR flags throughout: `Qwen3.8-27B-Q6_K` + mmproj, `-c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram
  auto -fa on --spec-type draft-mtp --draft-max 3 --kv-unified`.
- Harnesses in `split-prefill-73/`:
  - `resume_test.py A R` (`BIN_OVERRIDE`, `BUILD_TAG=1c5e564b`);
  - `static_kv_test.py VBR np4` (`TAG_SUFFIX=_1c5e`);
  - new: `resume_media_test.py`, run on both builds.
- Rows: `split-prefill-73/raw/{resume_test,static_kv_test,resume_media_test}.jsonl`.
- Logs: `raw_1c5e564b/*.log.gz` (home paths redacted).
- The daily driver was down for the window and restored through the wake proxy afterwards (`/wake`, 12:35).

This adds to `RESULT_FIX_0B2789F23_ON_73.md`: the same three tests on the new build, the displaced-slot gap that
receipt left open, and a new media round trip with the previous build as control.

## Results

| test | `0b2789f23` (09-25) | `1c5e564b` |
|---|---|---|
| `-np 1`: turn 1, 30 s idle, turn 2 | alive, 9,210 reused | **alive, 9,210 reused** (1.85 s) |
| `--resume` round trip (text, 9.2k) | save 41.6 s, 1.2 GB; `installed_full`; turn 2 reused 9,210 in 1.87 s | **save 17.9 s, 1.1 GB**; `installed_full`; turn 2 **reused 9,210 in 1.93 s** |
| `-np 4`: turn 3 after a tools-carrying side request displaced the conversation | `VBR host restore declined ... destination=invalid`; **full re-prefill, 64.5 s** | **`automatic VBR host restore source=0 prefix=9260 status=ok`, 333 ms**; turn 3 reused 9,260 in **2.27 s** |
| `-np 4`: turn 4 concurrent with a side request | both served, alive | both served (9,294 reused), **alive** |
| `--resume` with an **image** in turn 1 (9.4k incl. image) | save **skipped** (`reason: unsupported_positions`), 24 KB store; turn 2 **full re-prefill, 64.5 s** | **saved** 1.18 GB (17.9 s shutdown, 16.1 s of it the save); `installed_full`, 9,430 tokens incl. the image; turn 2 **reused 9,430 in 1.27 s** |

**Answers were correct on both builds:** "HARBOR 4729" for turn 1, and "red blue" after the restart. The control's
answer is right because turn 2 re-sends the image and it is re-processed. The difference between the builds is the
64 s re-prefill, not correctness.

## Details

- **The displacement still happens. What changed is the recovery.** The planner still sends the 569-token side
  request into the conversation's slot (`f_sim_best = 0.951, f_keep = 0.058`, the same decision as on `0b2789f23`
  and the static-KV build). The new build then captures the displaced conversation to host in the background
  (`VBR_IDLE_CAPTURE exact-background ... displaced=1`, 2.2 s). Turn 3 lands in an empty slot and restores it in
  333 ms. So the Hermes-subagent concern in the previous receipt is addressed.
- **Restart cost with a restored slot:** load 64.6 s against about 35 s without one. The install took 29.9 s
  (`install_done ... t_ms=29902`) for a 9.4k-token slot. That is paid once at startup instead of a 64 s re-prefill
  on the first turn.
- **The server now warns about a host-only restore:** "restored slot(s) have an exact host copy only: a continuation
  is warm, a diverging request prefil[ls]". This is expected: the continuation was warm.
- **Prefill and decode are unchanged:** ~150 tok/s prefill; the decode numbers are in the rows.

## Not fixed: the split-state stack overflow (`INCIDENT_73_META_SPLIT_STATE_STACK_OVERFLOW.md`)

`ggml/src/ggml-backend-meta.cpp:1211` still `clear()`s the whole `split_state_cache` on a `memcmp` mismatch. The
recursion that overflowed an 8 MB stack on 09-26 is therefore unchanged. It was **not re-tested**, because the
incident was never reproduced on demand. The daily driver keeps its 512 MiB `ulimit -s` mitigation.

## Not established

- One run per test, one conversation size (9.2k / 9.4k), one image.
- The displacement was triggered by a synthetic tools-carrying side request, not a real Hermes subagent.
- The resume round trip used a direct SIGTERM, not a wake-proxy suspend and wake cycle.
- The daily driver was not switched to `1c5e564b`; that is Mark's call.
