# buun `0b2789f23` fixes the tensor-split recurrent-capture abort on .73: `-np 1` idle reuse, `-np 4` and `--resume` all survive, and a conversation now survives a server restart. One gap remains: a VBR slot displaced at `-np 4` is not restored elsewhere

**2026-09-25 17:10-17:40, `.73`** (2x P100, `-sm tensor`), buun `0b2789f23` built in `~/buun-resume/build_sm60_resume`
(the daily cmake flags). The daily VBR flags throughout: `Qwen3.8-27B-Q6_K` + mmproj, `-c 262144 -ctk vbr -ctv vbr
--vbr-floor t4 --vbr-vram auto -fa on --spec-type draft-mtp --draft-max 3 --kv-unified`. Harness:
`split-prefill-73/resume_test.py` (rows tagged `"build": "0b2789f23"`) and `split-prefill-73/static_kv_test.py VBR
np4` (`BIN_OVERRIDE`, tag `_0b27`). Logs: `raw_fix_0b2789f23/*.log.gz` (home paths redacted).

**The fix:**
- `6c3cd4c52` "ggml-meta : get/set byte ranges that cut rows of a split tensor", followed by `7d3ac2474` and
  `51a215d7e` (one span path). The commit message names exactly the three paths reported in
  `INCIDENT_73_NP1_IDLE_REUSE_ABORT.md` / `RESULT_RESUME_2ACF5_ON_73.md`.
- The "sticky floor" part is `0b2789f23` itself: ROCm's `hipMemGetInfo` overcharges small VMM mappings. That is why it
  appeared on the 9070 and never on CUDA.

## Results

| test | before | `0b2789f23` |
|---|---|---|
| `-np 1`: turn 1, **30 s idle**, turn 2 extending it | abort, 4/4 (`08826ad6e`, `2acf5b10f`) | **alive**; turn 2 reused 9,210, prefilled 27 |
| `-np 4` VBR: turn 1, turn 2, side request, turn 3, then side concurrent with turn 4 | abort (`INCIDENT_73_NP4...`) | **alive through all six requests**; concurrent pair served |
| `--resume` round trip, tensor split: turn 1, SIGTERM, restart, turn 2 | shutdown save aborted; nothing restored | **saved** (41.6 s shutdown, 1.2 GB store); restart **`installed_full`**; turn 2 after the restart **reused 9,210, answered in 1.87 s** |

The restore-side `policy_mismatch` seen under `-sm layer` on `2acf5b10f` is also gone. The branch includes
`f0067d2be` "restore VBR slot files beside live slots" and `b65e391b2` ("tier_mismatch beside live slots").

## The remaining gap: a displaced VBR slot is not restored into another slot

In the `-np 4` run, the 569-token side request was placed **into the conversation's slot**:
`selected slot by LCP similarity, f_sim_best = 0.951, f_keep = 0.058`. It shares the ~540-token tools block with the
conversation, because the test's side request carries the same tools and Qwen3.8 renders tools first. The 9.2k
conversation was displaced, and turn 3 then went to an empty slot:

```
VBR host restore declined: status=unavailable validation=unavailable schedule=unavailable destination=invalid ...
edit/divergence sample ... = (0/9281/0/...)    # turn 3: full re-prefill, 64.5 s
```

The static-KV runs (`RESULT_STATIC_KV_WORKAROUND.md`, daily build) made **the same planner decision** (0.951 /
0.058), but turn 3 still reused 9,260: the fixed cache's host prompt cache restored the displaced conversation into
the empty slot. So the planner behaviour is shared. The **missing piece is VBR's host restore into an empty
destination slot**.

**Why it matters in practice:** a side request only displaces the conversation if it shares a long rendered prefix.
- Open WebUI's task calls and Hermes's compression call carry no tools, so they should land in empty slots.
- **Hermes subagents** (`delegate_task`) do share the tool list, and Qwen renders it before the system text. On VBR
  `-np 4` a subagent could displace the parent conversation, and the parent would then re-prefill.

## Other numbers

- **Resume save cost under tensor split:** 41.6 s shutdown and a 1.2 GB store for 9.2k tokens. Layer split on
  `2acf5b10f` wrote 675 MB in 8.5 s. The proxy's suspend waits a fixed 8 s after `pkill`; with `--resume` it must
  wait for the process to exit.
- Prefill ~150 tok/s and warm decode ~26 tok/s, unchanged from the daily build.

## Not established

- One run per test, and one conversation size (9.2k).
- The displacement case was triggered by a tool-carrying side request; a real Hermes subagent was not tested.
- `--resume` with a real multi-turn Hermes session across a proxy suspend/wake cycle is untested (needs the
  proxy's wait-for-exit change first).
