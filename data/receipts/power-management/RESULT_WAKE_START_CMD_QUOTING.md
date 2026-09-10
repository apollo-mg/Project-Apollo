# Wake-on-demand: the wake worked, the *launch* silently didn't — systemd ate the JSON quotes

**2026-08-28.** Mark woke `.73` through Hermes during a quota window. The machine woke; no model
loaded. Root cause was **not** power management, WoL, VBR, or VRAM.

## What the log showed

```
12:53:46 wake: sending magic packet
12:53:56 wake: node up after 10s          <- wake path perfect
12:53:56 start: launching llama-server
13:13:59 start: model never became healthy <- 20 minutes, no reason given
13:28:36 suspend: suspended
```

## Root cause

`WP_START_CMD` lives in a **double-quoted** systemd `Environment=` value. systemd strips bare
double quotes inside such a value, so:

```
--chat-template-kwargs '{"reasoning_effort":"medium"}'     # what was written
--chat-template-kwargs '{reasoning_effort:medium}'         # what llama-server received
```

llama-server rejected it during argument parsing and exited immediately:

```
error while handling argument "--chat-template-kwargs": [json.exception.parse_error.101]
parse error at line 1, column 2: ... last read: '{r'; expected string literal
```

Confirmed directly against the running unit:
`systemctl --user show apollo-wake-proxy.service -p Environment` printed
`chat-template-kwargs '{reasoning_effort:medium}'`.

**Fix:** escape as `'{\"reasoning_effort\":\"medium\"}'` in the unit file. A comment now sits
above the line so it is not reintroduced.

## Why it cost 20 minutes instead of 9 seconds

`start_cmd` backgrounds the server (`... & disown`), so **ssh returns rc=0 even when
llama-server dies during argument parsing**. The proxy then polled `/health` for the full
`WP_LOAD_TIMEOUT` (1200s) and reported only `model never became healthy`.

`start_server()` now also probes liveness and reports the reason:

- `pgrep -x llama-server` on the node (`-x`, exact process name — **never** `-f`, which would
  match the ssh command line carrying the pattern; that rule has been violated three times).
- After an 8s grace period, if the process is gone it stops waiting, greps the node-side server
  log for the first `error|failed|no such file|out of memory` line, and logs it.
- `/health OK` now records how long the load actually took.

A plain `tail -5` was tried first and was **worse than useless**: llama-server prints the reason
first and then a long usage blurb, so the tail showed the blurb and hid the cause.

## Verified end to end (not assumed)

| test | result |
|---|---|
| warm start through proxy | `/health OK after 55s`, HTTP 200 in 58.8s |
| **full cold cycle** (suspend -> request -> WoL -> load -> answer) | magic packet -> **up in 11s** -> `/health OK after 54s` -> **HTTP 200 in 97.5s**, `"Hello there, my good friend."` |
| context actually applied | `n_ctx = 262144` from `/props` |
| VBR KV active | `VBR dynamic runtime controller: KV budget auto ... floor 2.25 bits/value` |
| VRAM headroom | 11987 / 12353 MiB of 16384 per card |
| **failure path**, isolated proxy on :8098 with the original broken command | `llama-server EXITED after 9s — error while handling argument "--chat-template-kwargs" ...`, client gets HTTP 503 in 9.8s |

## The lesson worth keeping

I changed `WP_START_CMD` to the 262k VBR config when Mark asked for it and **never drove a cold
start through it**. The unit was restarted at 23:11; the last successful load was 22:19 — so the
new command had never once completed a load. The config looked right, and a config that looks
right is not a tested config.

This is the third variant of one recurring mistake: **treating a probe or a return code as proof
of readiness.** `/health` on llama-swap (fixed), `/v1/models` on the qwen4exp server earlier the
same day, and now `ssh rc=0` on a backgrounded launch. In every case something answered
successfully while the thing I actually cared about had not happened.

---

# Follow-up 2026-08-29 — the proxy 404'd every metadata endpoint

**Found by using it**: Mark woke `.73` from hermes-go on his phone. The wake worked perfectly —

```
10:45:15 wake: sending magic packet
10:45:26 wake: node up after 10s
10:46:23 start: /health OK after 57s
```

— but at **10:46**, inside that 57 s load window, the client showed:

```
Live chat unavailable (truncation parameters require confirm_truncate=true; an ordinary
prompt.submit must not drop session history). Saved on phone — will send when WebSocket reconnects.
```

and its context readout read **22.9k/131k**. After the model finished loading it read
**23.2k/262k** — the true value from our `-c 262144` config.

## Cause: only `/v1/*` was routed

`wake_proxy.py` exposed `/status`, `/wake`, `/suspend`, `/keepalive` and `/v1/{path:path}`.
llama.cpp's server publishes model metadata **outside** `/v1`:

| endpoint | through proxy (before) | direct to `.73` |
|---|---|---|
| `/props` | **404** | 200, `n_ctx = 262144` |
| `/health` | **404** | 200 |
| `/slots` | **404** | 200 |
| `/v1/models` | 200 | 200 |

A client that cannot read `n_ctx` falls back to a cached or default context length. That is the
most plausible source of the 131k figure and of the truncation parameters the gateway then
rejected — the client believed the window was far smaller than it was.

## Fix

Added `/props` and `/slots` passthrough routes that call `ensure_ready()` first (a client asking
for them intends to use the model, so waking is correct), plus an explicit `/health`.

**`/health` deliberately does NOT wake.** A monitoring poll must never spin up a sleeping
machine, and a 200 there must not be readable as "the model is loaded" — that error has now been
made twice on this project (llama-swap answering `/health`; `/v1/models` answering two seconds
into a four-minute load). It reports proxy liveness plus an honest `node: serving |
asleep_or_loading`.

Verified through the proxy: `/props` -> **200, `n_ctx = 262144`**; `/slots` -> 200;
`/health` -> 200 with `node: serving`; `/v1/models` unchanged.

**Scope:** verified on the warm path. The cold path was not re-exercised (the node was in use),
but the new routes call the same `ensure_ready()` gate as `/v1`, which was cold-tested end to end
on 2026-08-28 (wake 11 s, load 54 s, HTTP 200 in 97.5 s).

## Not ours — two hermes-go findings for O7

Attributing carefully, since three components are in this path (phone client, Tom's gateway, our
proxy):

1. **No dedup on reconnect.** The queued message ("Saved on phone — will send when WebSocket
   reconnects") produced **three copies** of the same user turn; two never received a reply and
   sat showing *"No reply yet — resend or edit this message"*. One succeeded.
2. **Model metadata is cached across a reload.** The session displayed 131k while the live server
   was 262k, and only corrected after an in-band `[System: The active model for this chat has
   changed to ...]` notice.

Both are aggravated by wake-on-demand, which is a deployment shape Tom likely has not tested
against: it creates a deterministic ~57 s window where the endpoint is reachable but the model is
not loaded. Worth reporting with exactly that framing.

---

# The ledger lost every endpoint, and the wake proxy became its floor (2026-08-29)

A desktop notification reported the ledger degraded. Heartbeat:

```json
{"status":"degraded","events":89,"reason":"no endpoint reachable; skeleton only"}
```

`tools/ledger_run.sh` tried three hosts, and **all three were gone**:

| endpoint | state |
|---|---|
| `10.0.0.194:8086` | dead — that box has been running qwen4exp tests on `:8087` |
| `10.0.0.194:8084` | dead |
| `127.0.0.1:8090` | dead — **the Ornith calibration server killed the night before** |

The third is the instructive one: it was never a durable endpoint, just a leftover from a failed
overnight run, and the ledger had been silently depending on it.

## Fix: the wake proxy as guaranteed last resort

```bash
HOSTS="${LEDGER_HOSTS:-http://10.0.0.194:8086 http://10.0.0.194:8084 http://127.0.0.1:8099}"
```

Order is a **cost** order, not a preference — already-running fleet servers first, then the proxy,
which is always reachable but spins up a sleeping box.

Two constraints recorded in the script:

- **It must be `:8099` (the proxy), never `.73:8080` direct.** The proxy tracks in-flight requests
  to decide when to suspend; a request that bypasses it is invisible, so `.73` could suspend
  **mid-generation**.
- **No timeout work was needed.** `ledger_build.py` already calls with `timeout=1800`, far above
  the ~97 s cold start. The proxy's own gate (`wake_timeout` 180 s + `load_timeout` 1200 s) also
  sits inside that.

## Verified against a genuinely sleeping node

`.73` suspended at 13:04:35, then `ledger_run.sh` invoked directly:

```json
{"status":"ok","events":74,"reason":"via http://127.0.0.1:8099"}
```

## The morning's ssh-retry fix fired on its first real job

```
13:05:00 start: launching llama-server
13:05:00 start: ssh attempt 1/3 failed rc=255: kex_exchange_identification: Connection reset by peer
13:06:00 start: /health OK after 54s
```

The `kex_exchange_identification` race — patched hours earlier from a **single** observed failure —
hit again on the very next cold start. Without the retry this scheduled run would have failed and
the ledger would have stayed degraded. Worth remembering the next time an intermittent failure
looks too rare to bother fixing.
