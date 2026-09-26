# Guest gateway: letting friends test the .73 model over Tailscale

`modules/guest_gateway.py` is an authenticated front door to the wake proxy. Guests get a key and one HTTPS URL on
the tailnet. Nothing else on the desktop should be reachable to them.

```
guest (their Tailscale) --HTTPS--> tailscale serve :443 --> guest_gateway 127.0.0.1:8098 --> wake_proxy :8099 --> .73
```

## What the gateway enforces (tested 2026-09-25)

| check | result |
|---|---|
| no key / wrong key / expired key | 401 |
| any route but `POST /v1/chat/completions` and `GET /v1/models` (`/slots`, `/warm`, ...) | 404 |
| malformed body, non-numeric `max_tokens` | 400 |
| `max_tokens` above the cap | clamped: asked 500 with the cap at 16, got exactly 16, `finish: length` |
| `id_slot` / `slot_id` / `n_keep` | dropped, so a guest cannot pick the daily driver's warm slot |
| a second guest request while one runs | 429, `Retry-After: 10` (default 1 guest request at a time) |
| node asleep | 503, `Retry-After: 60`, and ONE background wake. Tested against a fake upstream: repeated requests during the wake do not trigger more wakes; `/status` goes asleep -> waking -> ready |
| streaming | relayed as SSE; token counts are taken from the final usage chunk |
| usage log `run/guest_usage.jsonl` | who, when, status, token counts, seconds. **No prompt or reply text** |
| key storage `run/guest_keys.json` | sha256 only, mode 0600, gitignored; the key is printed once at creation |

## Day to day

```bash
./venv_cachyos/bin/python3 modules/guest_gateway.py add alice --days 7   # prints the key once; send it privately
./venv_cachyos/bin/python3 modules/guest_gateway.py list
./venv_cachyos/bin/python3 modules/guest_gateway.py revoke alice
./venv_cachyos/bin/python3 modules/guest_gateway.py serve               # 127.0.0.1:8098; GG_* env vars in the docstring
```

A guest points any OpenAI-compatible client at `https://<desktop>.<tailnet>.ts.net/v1` with their key. They should
**expect a 503 on the first request after the node has slept**, then retry after about 60 s. `/status` (no key
needed) says asleep / waking / ready.

## Deployment state (2026-09-25 ~22:45)

- **Tailnet policy:** saved by Mark. `autogroup:member` keeps full access to everything; `autogroup:shared` gets port
  443 only.
  - The guest rule is written as `"443"` (all protocols) rather than `"tcp:443"`. That is harmless, since nothing
    listens on UDP 443; tighten it when next editing.
  - Verified afterwards: the owner's access to .73 over the tailnet still works (ping 1 ms direct, :22 reachable).
- **Gateway:** running as a transient user unit, `systemd-run --user --unit=apollo-guest-gateway`, so it logs to the
  journal and does **not** start at boot. Stop it with `systemctl --user stop apollo-guest-gateway`.
- **`tailscale serve --bg --https=443`:** proxies to `127.0.0.1:8098`. The serve config persists across reboots; the
  gateway does not, so after a reboot the URL answers 502 until the gateway is started again.
  - Verified from the desktop over the real name: `/status` 200 with a valid Let's Encrypt certificate, chat
    without a key 401, `/slots` 404.
- **Not yet done:** sharing the desktop with a tester, and the guest-side port check (443 answers; 22, 445, 8099 do
  not).

## Step 2: exposing it on the tailnet (the procedure)

**Do this first, or sharing is unsafe.** Tailscale's default policy lets a user you share a machine with reach
*every* port on it. On the desktop that currently means:
- SSH (22) and SMB (139/445);
- the **unauthenticated** wake proxy (8099), which would bypass this gateway entirely;
- KDE Connect (1716) and anything else listening on all interfaces.

Before sharing, change the tailnet access policy (admin console -> Access controls) so that shared-in users reach
**only port 443 on the desktop**. Check the exact syntax against Tailscale's current docs when editing, since the
policy language (ACLs vs grants, and the autogroup for shared users) has changed over time. Then verify **from the
guest's side**: port 443 answers, and 22, 445 and 8099 do not.

Then:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:8098    # tailnet-only HTTPS with a real certificate
tailscale serve status
```

`tailscale serve` (not `funnel`) keeps it inside the tailnet. `funnel` would put it on the public internet, which
this gateway is not designed for.

`tailscale serve` also adds a `Tailscale-User-Login` header, which the usage log records next to the key name. The
log then shows which tailnet identity used which key.

## Not handled (proof of concept)

- A per-key daily token budget.
- Priority for the owner's own traffic beyond "one guest at a time". A guest's long prompt can still displace a
  warm slot (the displaced-slot restore gap measured on .73).
- Rate limits per key beyond the single concurrency slot.
- Running the gateway as a systemd unit. It is started by hand for now.
