# llm_proxy — transparent OpenAI-compatible logging proxy

Sits between an agent harness and llama-server and records what actually crossed the wire.

## Why

hermesbench writes `trace.jsonl` only when a task completes. In run `bitdepth_iq3xxs_v5`:

| outcome | trace.jsonl |
|---|---|
| PASS (14) | has data |
| FAIL (2) | has data |
| **INFRA_ERROR (13)** | **empty — all of them** |

Full data on every task that worked, none on any that failed — the exact inversion that hides a
runaway. The proxy exists so the failing case is the one we can still read afterwards.

## Use

```bash
python3 llm_proxy.py --listen 8091 --upstream http://127.0.0.1:8090 \
                     --log run.jsonl --pidfile proxy.pid
# then point the harness at http://127.0.0.1:8091/v1
kill $(cat proxy.pid)      # never `pkill -f llm_proxy.py` -- see AFM-37
```

Requires `aiohttp` (already in the hermesbench venv).

## What it logs (JSONL, flush+fsync per record)

- `request` — `n_msgs`, `roles`, `prompt_chars`, **`sys_sha`** (verify the "system prompt is
  byte-identical across tasks" claim instead of assuming it), `sys_chars`, `n_tools`,
  `max_tokens`, `stream`
- `progress` — every 256 chunks with a 200-char tail, so a hard kill bounds the loss
- `response` / **`aborted`** — `finish_reason`, `chunks`, `ttft`, `elapsed`, full text.
  `aborted` is written when the client disconnects mid-stream, i.e. when a task is killed.

## Measured properties

- **Overhead 0.2%**: 4.258 s proxied vs 4.249 s direct on an identical 128-token generation;
  TTFT unchanged (0.067 s vs 0.070 s). Chunks are forwarded before they are parsed.
- **No timeouts imposed** (`sock_read=None`) — a legitimate generation here can exceed 600 s.
- **Logging never breaks the run**: every log path is wrapped; failures print to stderr only.

## Verified before use

1. SSE passthrough — client receives byte-equivalent stream; `finish_reason` and full text logged.
2. **Abort capture** — client killed 0.9 s into a stream; proxy wrote `ev=aborted`, 18 chunks,
   98 chars of partial text. This is the capability the harness lacks.
3. End-to-end — `t04_search_grep/t01_basic` PASSes through the proxy; both chat calls captured,
   including a 17.49 s cold-prefill TTFT vs 0.355 s on the cached follow-up.

## Caveat

`ttft` and inter-chunk gaps are **proxy-side arrival times**, which include the loopback hop.
That is microseconds here, but they are not the server's internal timings — use the server log
for those.
