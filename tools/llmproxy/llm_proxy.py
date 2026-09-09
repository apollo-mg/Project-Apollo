#!/usr/bin/env python3
"""Transparent OpenAI-compatible logging proxy.

Sits between an agent harness and llama-server and records what actually crossed the wire.
Built because hermesbench writes trace.jsonl only on task completion: in run bitdepth_iq3xxs_v5
all 13 timed-out tasks had a 0-byte trace, so we had full data on every task that worked and
none on any that failed -- the exact inversion that hides a runaway.

Design constraints, in priority order:
  1. Never change what the harness observes. Chunks are forwarded the instant they arrive;
     nothing is buffered, no timeouts are imposed, and any logging error is swallowed.
  2. Never lose the failure. A partial generation is written when the client disconnects
     (task killed) and a progress record is fsynced every PROGRESS_EVERY chunks, so a hard
     kill of the proxy itself bounds the loss.
  3. Be honest about what it measures. ttft/gaps are proxy-side arrival times, which include
     network hop; on loopback that is microseconds, but it is not the server's internal timing.

Usage:
    llm_proxy.py --listen 8091 --upstream http://127.0.0.1:8090 --log run.jsonl
Point the harness at http://127.0.0.1:8091/v1 instead of 8090.
"""
import argparse, asyncio, hashlib, json, os, sys, time
from aiohttp import web, ClientSession, ClientTimeout

PROGRESS_EVERY = 256          # chunks between fsynced progress records
MAX_TEXT_CHARS = 400_000      # cap stored text per call; runaways are ~16k chars at 4096 tok

HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
              "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length"}


class Log:
    """Append-only JSONL. flush+fsync on demand (project rule: persist per item)."""
    def __init__(self, path):
        self.f = open(path, "a", buffering=1, encoding="utf-8")

    def write(self, rec, sync=False):
        try:
            self.f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.f.flush()
            if sync:
                os.fsync(self.f.fileno())
        except Exception as e:                      # logging must never break the benchmark
            print(f"[proxy] log error: {e}", file=sys.stderr)


def sha8(s):
    return hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()[:8]


def summarize_request(body):
    """Pull the fields worth correlating against server-side cache decisions."""
    msgs = body.get("messages") or []
    sys_msgs = [m for m in msgs if m.get("role") == "system"]
    sys_txt = "".join(str(m.get("content") or "") for m in sys_msgs)
    all_txt = "".join(str(m.get("content") or "") for m in msgs)
    return {
        "model": body.get("model"),
        "n_msgs": len(msgs),
        "roles": [m.get("role") for m in msgs][:12],
        "prompt_chars": len(all_txt),
        # lets us VERIFY the "system prompt is byte-identical across tasks" claim
        "sys_sha": sha8(sys_txt) if sys_txt else None,
        "sys_chars": len(sys_txt),
        "n_tools": len(body.get("tools") or []),
        "max_tokens": body.get("max_tokens"),
        "max_completion_tokens": body.get("max_completion_tokens"),
        "stream": bool(body.get("stream")),
        "temperature": body.get("temperature"),
    }


def parse_sse_delta(raw):
    """Return (text_delta, finish_reason) from one SSE line block. Tolerant by design."""
    text, finish = "", None
    for line in raw.split("\n"):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        for ch in obj.get("choices") or []:
            d = ch.get("delta") or {}
            for k in ("content", "reasoning_content"):
                if isinstance(d.get(k), str):
                    text += d[k]
            if ch.get("finish_reason"):
                finish = ch["finish_reason"]
    return text, finish


class Proxy:
    def __init__(self, upstream, log):
        self.upstream, self.log = upstream.rstrip("/"), log
        self.n = 0

    async def handle(self, request):
        self.n += 1
        cid = self.n
        url = self.upstream + request.path_qs
        raw = await request.read()

        body, meta = None, {}
        if raw:
            try:
                body = json.loads(raw)
                if isinstance(body, dict) and "messages" in body:
                    meta = summarize_request(body)
            except Exception:
                pass

        t0 = time.time()
        self.log.write({"t": t0, "ev": "request", "id": cid, "method": request.method,
                        "path": request.path, **meta}, sync=True)

        headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
        # No timeouts anywhere: a legitimate generation here can exceed 600s.
        timeout = ClientTimeout(total=None, connect=30, sock_connect=30, sock_read=None)

        try:
            async with ClientSession(timeout=timeout, auto_decompress=False) as sess:
                async with sess.request(request.method, url, data=raw or None,
                                        headers=headers, allow_redirects=False) as up:
                    resp_headers = {k: v for k, v in up.headers.items()
                                    if k.lower() not in HOP_BY_HOP}
                    out = web.StreamResponse(status=up.status, headers=resp_headers)
                    await out.prepare(request)

                    text, finish, nchunks, ttft, aborted = "", None, 0, None, False
                    try:
                        async for chunk in up.content.iter_any():
                            # forward FIRST -- observation must not delay the harness
                            await out.write(chunk)
                            nchunks += 1
                            if ttft is None:
                                ttft = time.time() - t0
                            try:
                                d, f = parse_sse_delta(chunk.decode("utf-8", "replace"))
                                if d and len(text) < MAX_TEXT_CHARS:
                                    text += d
                                if f:
                                    finish = f
                            except Exception:
                                pass
                            if nchunks % PROGRESS_EVERY == 0:
                                self.log.write({"t": time.time(), "ev": "progress", "id": cid,
                                                "chunks": nchunks, "text_chars": len(text),
                                                "elapsed": time.time() - t0,
                                                "tail": text[-200:]}, sync=True)
                    except (asyncio.CancelledError, ConnectionResetError):
                        aborted = True                       # client (task) was killed mid-stream
                    except Exception as e:
                        aborted = True
                        self.log.write({"t": time.time(), "ev": "stream_error", "id": cid,
                                        "error": repr(e)}, sync=True)

                    # Non-streaming replies arrive as one blob; recover finish_reason from it.
                    if finish is None and not meta.get("stream") and text == "" and nchunks:
                        pass

                    self.log.write({"t": time.time(),
                                    "ev": "aborted" if aborted else "response",
                                    "id": cid, "status": up.status, "finish_reason": finish,
                                    "chunks": nchunks, "ttft": ttft,
                                    "elapsed": time.time() - t0,
                                    "text_chars": len(text), "text_sha": sha8(text) if text else None,
                                    "text": text}, sync=True)
                    await out.write_eof()
                    return out
        except Exception as e:
            self.log.write({"t": time.time(), "ev": "proxy_error", "id": cid,
                            "error": repr(e)}, sync=True)
            return web.json_response({"error": {"message": f"proxy: {e}"}}, status=502)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", type=int, default=8091)
    ap.add_argument("--upstream", default="http://127.0.0.1:8090")
    ap.add_argument("--log", required=True)
    ap.add_argument("--host", default="127.0.0.1")
    # Write a pidfile so callers can stop this by PID. Never `pkill -f llm_proxy.py`: any command
    # block that also *mentions* the script name matches its own shell and kills the caller.
    # Bracketing the pattern ([l]lm_proxy.py) does NOT save you when the literal string appears
    # elsewhere in the same block -- that is how this was learned, twice. See AFM-37.
    ap.add_argument("--pidfile", default=None)
    a = ap.parse_args()

    if a.pidfile:
        with open(a.pidfile, "w") as f:
            f.write(str(os.getpid()))
    log = Log(a.log)
    log.write({"t": time.time(), "ev": "proxy_start", "listen": a.listen,
               "upstream": a.upstream, "pid": os.getpid()}, sync=True)
    p = Proxy(a.upstream, log)
    app = web.Application(client_max_size=1024**3)
    app.router.add_route("*", "/{tail:.*}", p.handle)
    print(f"[proxy] {a.host}:{a.listen} -> {a.upstream}  log={a.log}", flush=True)
    web.run_app(app, host=a.host, port=a.listen, print=None, access_log=None)


if __name__ == "__main__":
    main()
