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

## Step 2: exposing it on the tailnet (NOT done yet; needs Mark's go-ahead)

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
