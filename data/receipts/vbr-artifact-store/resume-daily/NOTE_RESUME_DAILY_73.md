# Note -- `--resume` is live on the .73 daily driver and survives a real proxy suspend/wake: turn 2 re-prefilled 27 tokens instead of 8,374 (restored from an NVMe store). The restore runs at startup (+28 s for 8.4k tokens), so for short conversations it is time-neutral; it pays for long ones.

**2026-10-02**, Mark: "that sounds like a solid plan to start with." Closes BACKLOG N2's open item: a real
`--resume` across a proxy suspend/wake.

**Prior art:** `RESULT_1C5E564B_ON_73.md` (09-27) verified the `--resume` round trip with a direct restart on the same
build line. **What this adds:** the daily unit, the wake proxy's suspend path, the store on the NVMe, and the cost of a
wake.

## Change

- **Unit** (`~/.config/systemd/user/apollo-wake-proxy.service`; backup `.bak-20261002-preresume`):
  - the start command creates `~/vbr-store` and adds `--resume --resume-path ~/vbr-store`;
  - `WP_RESUME_STORE` and `WP_RESUME_WARN_GB=20` are set.
- **`modules/wake_proxy.py`:** `check_resume_store()` runs after the server has exited at each suspend, when the save
  is complete. It logs the store size and sends a `notify-send` past 20 GB. **It never deletes anything.**
  - buun's own retention bounds the store by count: 2 entries for this config, at most 8 overall.
  - An entry can point into another entry's artifact (a placement), so a byte cap needs a manifest-aware pruner.
    Deferred until the warning ever fires.
- **Store:** the root NVMe, 110 GB free.

## Test (through the proxy, `resume_proxy_test.py`; rows `rows.jsonl`)

| step | result |
|---|---|
| turn 1 (cold wake + load) | 8,366 prompt tokens in 47.8 s; answer "HARBOR 4729" (correct) |
| `POST /suspend` | server shutdown and save 29 s; `saved` 8,374 tokens, 1.18 GB (`t_ms` 26,089, 2 tail states); proxy logged `resume store: 1.18 GB`; node suspended |
| turn 2 (wake + load + restore) | `installed_full`, 1 entry, `t_ms` 28,431; **prompt 27 tokens (cache 8,374) in 0.8 s**; answer "red blue" (correct) |

**Time from request to answer:** turn 2 took 92 s in total: wake 8 s, then load to health 67 s (35 s without a
restore), then the request. A cold continuation would have taken ~95 s (load 35 s + re-prefill ~48 s).

## What it means

- **It works on the daily path,** and the proxy's wait-for-exit covers the save.
- **The cost moves from the first request to every wake.** The restore (~3.4 ms per saved token) blocks startup,
  even when the next request is unrelated.
  - Prefill costs 5.7 ms/token at 8k and grows with depth, so resume wins on long conversations and roughly ties at
    8k.
  - buun warns: "a continuation is warm, a diverging request prefills cold".
- **Watch:** the proxy's exit wait is 300 s. At ~3.5 ms per saved token, more than ~85k saved tokens across both
  slots would hit the SIGKILL and lose the save. Raise it if long Hermes sessions become routine.

## Not established

- A real Hermes session (tools, long system head) across a suspend; the warm-on-load head was not saved as a second
  entry here.
- Restores of 2 entries, and of long (50k+) conversations.
- Whether a lazy (on-demand) install exists or would help.

## 10-03 update: the host prompt cache was being persisted too; fixed with `--resume-no-host-cache`

- **What happened overnight:**
  - By default `--resume` also saves every conversation in buun's host prompt cache, up to the 8-entry overall
    retention. The nightly daydream filled it.
  - A shutdown with both slots empty still logged `capture_done slots=0 hosted=8`, 79 s, 1.1 GB of it the
    daydream's 14k-token chat.
  - Every wake then restored all 8 (`installed_host`, ~8 s each): healthy at 125-134 s instead of 35 s.
- **Erasing the slots after the daydream (`tools/daydream_nightly.sh`) was not enough on its own,** since the
  erased conversations live on in the host cache.
- **The flag `--resume-no-host-cache`** ("--resume for the slots only") arrived in buun `f08683ffa` (09-28), one
  day after the daily build.
  - The unmodified daily binary rejected it ("invalid argument"; the daily driver was down ~2.5 min during that
    try, unit restored from backup).
  - **Fix:** the 21-line commit was cherry-picked onto the exact daily commit (`510cbbbfa` + `f08683ffa` =
    `ccb273321`, local branch) and built with the daily CMake options at `/mnt/HDD/buun-510cb-nohost`
    (`llama-server` sha256 `02c391b8...`). The unit points there; the old build is untouched.
  - Unit backup: `.bak-20261003-hostcache`.
- **The flag changes buun's resume key,** so the 8 old host entries now read as another key: never restored, and
  trimmed by the overall bound as new entries arrive (~3 GB on disk meanwhile).

| | before (host cache saved) | after (`--resume-no-host-cache`) |
|---|---|---|
| save at suspend | `slots=0 hosted=8`, 79 s | `slots=1 hosted=0`, 14 s |
| restore at wake | 8 host entries | `installed_full` 1 entry (8,374 tokens), `host=0` |
| health after wake, store empty for this key | 125-134 s | **35 s** |
| health after wake, one 8.4k conversation | n/a | 65 s (restore 28.6 s) |
| turn 2 | | prompt 27 tokens, cache 8,374, answer correct |

**With the nightly slot erase:** the daydream's own conversations are no longer saved. Mark's saved entries survive
it: retention never deletes an entry just because its conversation is not in a slot at save time.
