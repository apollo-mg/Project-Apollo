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
