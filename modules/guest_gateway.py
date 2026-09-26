#!/usr/bin/env python3
"""Guest gateway: a small authenticated front door to the .73 wake proxy, for letting friends test the model.

    guest client --(Tailscale serve, HTTPS)--> guest_gateway (127.0.0.1:8098) --> wake_proxy (:8099) --> .73

The wake proxy has no authentication and listens on every interface; it must never be what a guest reaches. This
gateway is the only thing a guest should be able to touch, and it:
  * requires a per-person key (Authorization: Bearer gk_...). Only the key's sha256 is stored, in run/guest_keys.json
    (gitignored), with an expiry;
  * forwards exactly two routes, POST /v1/chat/completions and GET /v1/models, and 404s everything else (/slots,
    /warm, /props, slot save/restore, ...);
  * clamps max_tokens, caps the request body, and drops fields that pick a server slot, so a guest cannot target
    the daily driver's warm cache;
  * admits GG_GUEST_CONCURRENCY guest requests at a time (default 1) and answers 429 + Retry-After beyond that
    (admission control, not an unbounded queue);
  * on a sleeping node, starts the wake in the background and answers 503 + Retry-After at once. The wake takes
    55-77 s, and most client libraries time out before that if the connection is held;
  * logs one line per request to run/guest_usage.jsonl: who, when, status and token counts. Never prompt or reply
    text.

    guest_gateway.py add NAME [--days 7]    # prints the key ONCE; only its hash is kept
    guest_gateway.py list | revoke NAME
    guest_gateway.py serve                  # GG_HOST (default 127.0.0.1), GG_PORT (default 8098)
"""
from __future__ import annotations
import argparse, asyncio, datetime as dt, hashlib, hmac, json, os, secrets, sys, time
from pathlib import Path
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

ROOT = Path(__file__).resolve().parents[1]
KEYS = Path(os.getenv("GG_KEYS", ROOT / "run/guest_keys.json"))
USAGE = Path(os.getenv("GG_LOG", ROOT / "run/guest_usage.jsonl"))
UPSTREAM = os.getenv("GG_UPSTREAM", "http://127.0.0.1:8099")
MAX_TOKENS = int(os.getenv("GG_MAX_TOKENS", "4096"))
MAX_BODY = int(os.getenv("GG_MAX_BODY", str(256 * 1024)))
CONCURRENCY = int(os.getenv("GG_GUEST_CONCURRENCY", "1"))
RETRY_WAKE = int(os.getenv("GG_RETRY_AFTER", "60"))
SLOT_FIELDS = ("id_slot", "slot_id", "n_keep")          # fields that address server slots / cache layout


def _load_keys() -> dict:
    try:
        return json.loads(KEYS.read_text())
    except (OSError, ValueError):
        return {"keys": []}


def _save_keys(d: dict) -> None:
    KEYS.parent.mkdir(parents=True, exist_ok=True)
    tmp = KEYS.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.chmod(tmp, 0o600)
    tmp.replace(KEYS)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def who(auth: str | None) -> str | None:
    """Key owner's name for a valid, unexpired bearer key, else None. Constant-time compare on the hash."""
    if not auth or not auth.startswith("Bearer "):
        return None
    h = _sha(auth[7:].strip())
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for k in _load_keys()["keys"]:
        if hmac.compare_digest(k["sha256"], h) and k["expires"] > now:
            return k["name"]
    return None


def _usage(rec: dict) -> None:
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    with open(USAGE, "a") as f:
        f.write(json.dumps(rec) + "\n")


def build_app():
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    gate = asyncio.Semaphore(CONCURRENCY)
    waking: dict = {"task": None}

    def err(code: int, msg: str, retry: int | None = None):
        h = {"Retry-After": str(retry)} if retry else {}
        return JSONResponse({"error": {"message": msg, "code": code}}, status_code=code, headers=h)

    async def node_state() -> str:
        try:
            async with httpx.AsyncClient(timeout=5) as cl:
                s = (await cl.get(f"{UPSTREAM}/status")).json()
        except (httpx.HTTPError, ValueError):
            return "unavailable"
        if s.get("serving"):
            return "ready"
        t = waking["task"]      # proxy states: unknown waking unreachable loading load-failed serving suspended
        return "waking" if (t and not t.done()) or s.get("state") in ("waking", "loading") else "asleep"

    async def wake_in_background() -> None:
        async def _w():
            async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=10)) as cl:
                await cl.post(f"{UPSTREAM}/wake")
        if waking["task"] is None or waking["task"].done():
            waking["task"] = asyncio.create_task(_w())

    @app.get("/status")
    async def status():
        """Unauthenticated and deliberately minimal: asleep / waking / ready, nothing about the host."""
        st = await node_state()
        return {"state": st, "retry_after": RETRY_WAKE if st in ("asleep", "waking") else 0,
                "note": "first request after a sleep wakes the node (~60 s): expect 503 + Retry-After, then retry"}

    @app.get("/v1/models")
    async def models(request: Request):
        name = who(request.headers.get("authorization"))
        if not name:
            return err(401, "missing or invalid key")
        if await node_state() != "ready":
            await wake_in_background()
            return err(503, "the node is asleep and is waking up; retry shortly", RETRY_WAKE)
        async with httpx.AsyncClient(timeout=30) as cl:
            r = await cl.get(f"{UPSTREAM}/v1/models")
        return JSONResponse(r.json(), status_code=r.status_code)

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        t0 = time.time()
        name = who(request.headers.get("authorization"))
        if not name:
            return err(401, "missing or invalid key")
        raw = await request.body()
        if len(raw) > MAX_BODY:
            return err(413, f"request body over {MAX_BODY} bytes")
        try:
            body = json.loads(raw)
            assert isinstance(body, dict) and isinstance(body.get("messages"), list)
        except (ValueError, AssertionError):
            return err(400, "body must be a JSON chat-completions request with a messages list")
        for f in SLOT_FIELDS:
            body.pop(f, None)
        try:
            for f in ("max_tokens", "max_completion_tokens", "n_predict"):
                if f in body:
                    body[f] = min(int(body[f]), MAX_TOKENS)
        except (TypeError, ValueError):
            return err(400, "max_tokens must be an integer")
        if not any(f in body for f in ("max_tokens", "max_completion_tokens", "n_predict")):
            body["max_tokens"] = MAX_TOKENS
        rec = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "who": name,
               "tailscale_user": request.headers.get("tailscale-user-login"), "stream": bool(body.get("stream"))}
        st = await node_state()
        if st != "ready":
            await wake_in_background()
            _usage({**rec, "status": 503, "why": f"node {st}"})
            return err(503, "the node is asleep and is waking up; retry shortly", RETRY_WAKE)
        if gate.locked():
            _usage({**rec, "status": 429, "why": "guest slot busy"})
            return err(429, "another guest request is running; retry shortly", 10)
        await gate.acquire()
        cl = httpx.AsyncClient(timeout=httpx.Timeout(900, connect=10))
        if not body.get("stream"):
            try:
                r = await cl.post(f"{UPSTREAM}/v1/chat/completions", json=body)
                try:
                    j = r.json()
                except ValueError:
                    j = None
                u = (j.get("usage") or {}) if isinstance(j, dict) else {}
                _usage({**rec, "status": r.status_code, "prompt_tokens": u.get("prompt_tokens"),
                        "completion_tokens": u.get("completion_tokens"), "secs": round(time.time() - t0, 1)})
                if j is None:
                    return Response(r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))
                return JSONResponse(j, status_code=r.status_code)
            finally:
                await cl.aclose(); gate.release()

        body.setdefault("stream_options", {"include_usage": True})
        req = cl.build_request("POST", f"{UPSTREAM}/v1/chat/completions", json=body)
        try:
            r = await cl.send(req, stream=True)
        except httpx.HTTPError as e:                  # never leave the guest slot held by a failed connect
            await cl.aclose(); gate.release()
            _usage({**rec, "status": 502, "why": type(e).__name__})
            return err(502, "upstream unavailable")

        async def relay():
            usage = {}
            try:
                async for line in r.aiter_lines():
                    if line.startswith("data: {") and '"usage"' in line:
                        try:
                            usage = json.loads(line[6:]).get("usage") or usage
                        except ValueError:
                            pass
                    yield line + "\n"
            finally:
                await r.aclose(); await cl.aclose(); gate.release()
                _usage({**rec, "status": r.status_code, "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"), "secs": round(time.time() - t0, 1)})
        return StreamingResponse(relay(), status_code=r.status_code, media_type="text/event-stream")

    return app


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_add = sub.add_parser("add"); a_add.add_argument("name"); a_add.add_argument("--days", type=float, default=7)
    sub.add_parser("list")
    a_rev = sub.add_parser("revoke"); a_rev.add_argument("name")
    sub.add_parser("serve")
    a = ap.parse_args()
    d = _load_keys()
    if a.cmd == "add":
        if any(k["name"] == a.name for k in d["keys"]):
            sys.exit(f"{a.name} already has a key; revoke it first")
        key = "gk_" + secrets.token_urlsafe(24)
        exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=a.days)
        d["keys"].append({"name": a.name, "sha256": _sha(key), "created": dt.datetime.now(dt.timezone.utc).isoformat(),
                          "expires": exp.isoformat()})
        _save_keys(d)
        print(f"key for {a.name} (shown once, expires {exp:%Y-%m-%d %H:%M} UTC):\n{key}")
    elif a.cmd == "list":
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        for k in d["keys"]:
            print(f"{k['name']:20s} expires {k['expires'][:16]}  {'active' if k['expires'] > now else 'EXPIRED'}")
    elif a.cmd == "revoke":
        n = len(d["keys"]); d["keys"] = [k for k in d["keys"] if k["name"] != a.name]; _save_keys(d)
        print(f"revoked {n - len(d['keys'])} key(s) for {a.name}")
    else:
        import uvicorn
        uvicorn.run(build_app(), host=os.getenv("GG_HOST", "127.0.0.1"), port=int(os.getenv("GG_PORT", "8098")))


if __name__ == "__main__":
    main()
