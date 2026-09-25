#!/usr/bin/env python3
"""Wake-on-demand proxy: an OpenAI-compatible endpoint in front of a node that sleeps.

The node (.73) idles at ~100-120 W producing heat in a room that is already too warm half the
year, and is used as a FLEX machine -- busy in bursts, idle for days. This holds it in S3 and
brings it back only when a request actually arrives.

  client -> :8099/v1/chat/completions -> [node asleep?] -> WoL -> start llama-server -> proxy

Verified preconditions (data/receipts/power-management/RESULT_S3_WOL_CYCLE.md):
  * the P100s survive deep S3 and resume with persistence mode intact, 0 Xids
  * Wake-on-LAN via magic packet works (`Wake-on: g` already enabled)
  * /var has 24 GiB against 32 GiB of VRAM, so we ALWAYS unload before suspending rather than
    relying on NVreg_PreserveVideoMemoryAllocations. Resume costs a model load, not a spill.

Design notes that matter:
  * one asyncio.Lock guards the whole wake path -- ten concurrent requests must produce ONE
    magic packet and ONE server launch, not ten.
  * an in-flight counter blocks suspend while any request is open, independent of the idle
    timer. A long generation must never be suspended out from under a client.
  * cold start is slow (wake + model load). Streaming clients get SSE comments as keepalive so
    proxies and browsers do not drop the connection; non-streaming clients simply block.
"""
from __future__ import annotations
import asyncio, json, os, socket, subprocess, time
from dataclasses import dataclass, field
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

@dataclass
class Cfg:
    host: str = os.getenv("WP_NODE", "10.0.0.73")
    mac: str = os.getenv("WP_MAC", "e0:d5:5e:b5:9e:b3")
    bcast: str = os.getenv("WP_BCAST", "10.0.0.255")
    port: int = int(os.getenv("WP_LLAMA_PORT", "8080"))
    # command run over ssh to bring the model up; MUST daemonise and return.
    start_cmd: str = os.getenv("WP_START_CMD", "")
    idle_secs: int = int(os.getenv("WP_IDLE", "1800"))      # 30 min before unload+suspend
    wake_timeout: int = int(os.getenv("WP_WAKE_TIMEOUT", "180"))
    load_timeout: int = int(os.getenv("WP_LOAD_TIMEOUT", "600"))
    enable_suspend: bool = os.getenv("WP_SUSPEND", "1") == "1"
    fail_cooldown: int = int(os.getenv("WP_FAIL_COOLDOWN", "60"))
    # where start_cmd redirects llama-server output on the node; read back on failure so a
    # bad launch reports its own reason instead of timing out silently.
    server_log: str = os.getenv("WP_SERVER_LOG", "/home/mark/wake_proxy_server.log")

C = Cfg()
LOG = os.getenv("WP_LOG", "/mnt/TG_2TB/Projects/Apollo/run/wake_proxy.log")
WARM_FILE = os.getenv("WP_WARM_FILE", "/mnt/TG_2TB/Projects/Apollo/run/warm_head.json")
WARM_MIN_CHARS = int(os.getenv("WP_WARM_MIN_CHARS", "4000"))   # agent heads only, not chat UIs
WARM_TIMEOUT = float(os.getenv("WP_WARM_TIMEOUT", "1800"))
# OFF by default in code (2026-09-24): on buun 08826ad6e + -sm tensor + VBR, the first chat after a fresh-server warm-up
# aborted llama-server (ggml-backend-meta.cpp:1783). FIXED in buun 0b2789f23 (vbr-artifact-store/RESULT_FIX_0B2789F23_ON_73.md);
# the .73 unit sets WP_WARM_ON_LOAD=1.
WARM_ON_LOAD = os.getenv("WP_WARM_ON_LOAD", "0") == "1"

def _redate(system: str) -> str:
    """Hermes stamps 'Conversation started: <Weekday>, <Month> <DD>, <YYYY>' (date-only, so the head is
    byte-stable for a day). A head captured yesterday must be re-dated or reuse stops at that line.
    Multi-day sessions add a 'Today's date (as of the last context rebuild)' line a new session lacks."""
    import re
    today = time.strftime("%A, %B %d, %Y")
    system = re.sub(r"(Conversation started: )[A-Z][a-z]+, [A-Z][a-z]+ \d{2}, \d{4}", r"\g<1>" + today, system)
    return re.sub(r"\nToday's date \(as of the last context rebuild\):[^\n]*", "", system)

def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n"); f.flush(); os.fsync(f.fileno())   # standing rule: persist per item
    except OSError:
        pass

def magic_packet(mac: str, bcast: str) -> None:
    pkt = b"\xff" * 6 + bytes.fromhex(mac.replace(":", "").replace("-", "")) * 16
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    for p in (9, 7):
        s.sendto(pkt, (bcast, p))
    s.close()

async def ssh(host: str, cmd: str, timeout: int = 30) -> tuple[int, str]:
    p = await asyncio.create_subprocess_exec(
        "ssh", "-n", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", host, cmd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(p.communicate(), timeout)
    except asyncio.TimeoutError:
        p.kill(); return 255, "ssh timeout"
    return p.returncode, out.decode(errors="replace").strip()


class Node:
    """All node state transitions. Every method is safe to call when the node is asleep."""
    def __init__(self, cfg: Cfg):
        self.c = cfg
        self.lock = asyncio.Lock()
        self.inflight = 0
        self.last_request = time.time()
        self.state = "unknown"
        # Without this, a FAILED wake is retried by every queued caller in turn: the lock
        # serialises them, so 5 requests become 5 sequential wake timeouts and callers 2..5
        # wait N x wake_timeout before hearing anything. Cache the failure briefly so the herd
        # fails fast, and let the next request after the cooldown try again.
        self._fail_until = 0.0

    @property
    def base(self) -> str:
        return f"http://{self.c.host}:{self.c.port}"

    async def serving(self, timeout: float = 3.0) -> bool:
        try:
            async with httpx.AsyncClient(timeout=timeout) as cl:
                return (await cl.get(self.base + "/health")).status_code == 200
        except Exception:
            return False

    async def server_alive(self) -> bool:
        """Is llama-server actually running on the node? start_cmd daemonises, so ssh's rc says
        nothing about whether the server survived its own argument parsing."""
        rc, _ = await ssh(self.c.host, "pgrep -x llama-server >/dev/null", timeout=10)
        return rc == 0

    async def reachable(self) -> bool:
        rc, _ = await ssh(self.c.host, "true", timeout=8)
        return rc == 0

    async def wake(self) -> bool:
        log(f"wake: sending magic packet to {self.c.mac}")
        magic_packet(self.c.mac, self.c.bcast)
        deadline = time.time() + self.c.wake_timeout
        while time.time() < deadline:
            if await self.reachable():
                log(f"wake: node up after {self.c.wake_timeout - (deadline - time.time()):.0f}s")
                return True
            await asyncio.sleep(2)
            magic_packet(self.c.mac, self.c.bcast)     # cheap; some NICs miss the first
        log("wake: TIMED OUT — node may need a physical power-on")
        return False

    async def start_server(self) -> bool:
        # MANAGED MODE (start_cmd empty) is the normal case on a node that already runs a model
        # manager. .73 runs llama-swap as its single serving entry point: systemd-enabled,
        # exclusive-group loading, on-demand swaps. Launching our own llama-server there fights
        # it for the port -- the bind fails, llama-swap answers /health anyway, and we declare
        # a model "loaded" that never loaded. Wait for the manager instead; it loads on demand
        # when the request arrives.
        if not self.c.start_cmd:
            deadline = time.time() + self.c.load_timeout
            while time.time() < deadline:
                if await self.serving():
                    log("start: model manager healthy (managed mode — it loads on demand)")
                    return True
                await asyncio.sleep(2)
            log("start: model manager never became healthy")
            return False
        log("start: launching llama-server")
        # sshd is not reliably ready the instant the box answers a first connection after S3
        # resume: wake() returns on one successful ssh, and the very next one can be reset mid
        # key exchange (`kex_exchange_identification: read: Connection reset by peer`, observed
        # 2026-08-29). Retry the transport. A non-zero rc here is an SSH failure, never a bad
        # llama-server flag -- start_cmd backgrounds the server, so a broken command still
        # exits 0 and is caught later by the liveness probe.
        rc, out = -1, ""
        for attempt in range(1, 4):
            rc, out = await ssh(self.c.host, self.c.start_cmd, timeout=120)
            if rc == 0:
                break
            log(f"start: ssh attempt {attempt}/3 failed rc={rc}: {out[:120]}")
            await asyncio.sleep(5)
        if rc != 0:
            log(f"start: launch command failed after 3 attempts rc={rc}: {out[:200]}")
            return False
        deadline = time.time() + self.c.load_timeout
        launched_at = time.time()
        while time.time() < deadline:
            if await self.serving():
                log(f"start: /health OK after {time.time() - launched_at:.0f}s")
                return True
            # A server that exits during argument parsing is dead within a second, but the
            # backgrounded ssh still returned rc=0. Without this the proxy waits out the whole
            # load_timeout (20 min, observed 2026-08-28) and reports nothing useful.
            if time.time() - launched_at > 8 and not await self.server_alive():
                # prefer the actual error line: llama-server prints the reason first and then
                # a long usage blurb, so a plain tail shows the blurb and hides the cause.
                _, tail = await ssh(self.c.host,
                    f"grep -iE 'error|failed|no such file|out of memory' {self.c.server_log} | head -3 "
                    f"|| tail -3 {self.c.server_log}", timeout=15)
                log(f"start: llama-server EXITED after {time.time() - launched_at:.0f}s — {tail}")
                return False
            await asyncio.sleep(3)
        log(f"start: model never became healthy within {self.c.load_timeout}s (process still alive)")
        return False

    async def ensure_ready(self) -> tuple[bool, str]:
        """Idempotent, single-flight. Concurrent callers wait on one wake, not N."""
        if await self.serving():
            return True, "already serving"
        if time.time() < self._fail_until:
            return False, f"wake failed recently; retrying in {self._fail_until - time.time():.0f}s"
        async with self.lock:
            # Cooldown BEFORE the serving() re-check: the cooldown test is free, serving() costs
            # a 3s network timeout. Waiters released from a FAILED wake would otherwise each pay
            # that timeout in turn, producing a 3s staircase across the queue. On a SUCCESSFUL
            # wake _fail_until is cleared, so this falls through to serving() as intended.
            if time.time() < self._fail_until:
                return False, f"wake failed recently; retrying in {self._fail_until - time.time():.0f}s"
            if await self.serving():                    # re-check: another caller may have won
                return True, "serving (raced)"
            # Cancel any suspend armed by the idle monitor. Without this a wake races a deferred
            # `systemd-run --on-active` timer and the node sleeps mid-load.
            await ssh(self.c.host,
                      "sudo -n systemctl stop apollo-suspend.timer apollo-suspend.service "
                      "2>/dev/null || true", timeout=15)
            if not await self.reachable():
                self.state = "waking"
                if not await self.wake():
                    self.state = "unreachable"
                    self._fail_until = time.time() + self.c.fail_cooldown
                    return False, "wake failed — node did not come up"
            # The idle monitor measures (now - last_request), and /wake never touched it: after
            # any real sleep that value is already past idle_secs, so the monitor's next 60s tick
            # suspended the node we had just woken. Observed twice on 2026-09-08 -- the second
            # time mid-load, which killed llama-server and was then reported as "model failed to
            # load", naming the wrong cause. Bringing the node up IS intent to use it, so start
            # the clock here: the whole load window is protected, not just the success instant.
            self.last_request = time.time()
            self.state = "loading"
            if not await self.start_server():
                self.state = "load-failed"
                self._fail_until = time.time() + self.c.fail_cooldown
                return False, "node awake but model failed to load"
            self.state = "serving"
            self._fail_until = 0.0
            self.last_request = time.time()     # a completed load restarts the idle clock
            return True, "woken and loaded"

    async def busy(self) -> bool:
        """Never suspend on top of real work, even if our own idle timer says otherwise."""
        if self.inflight:
            return True
        # `timeout 10` runs REMOTELY and is load-bearing. The ssh helper's own timeout kills the
        # LOCAL client; the remote command keeps running. nvidia-smi can block indefinitely on a
        # faulted GPU, so an unbounded poll here leaks one stuck remote process per minute,
        # forever. On 2026-09-19 a ~1 Hz poller with the same flaw put .73 at load 770 with 862
        # resident nvidia-smi. See data/receipts/agentic-ladder/INCIDENT_73_NVIDIA_SMI_PILEUP.md
        rc, out = await ssh(self.c.host,
            "timeout 10 nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits",
            timeout=15)
        if rc == 0 and any(int(x) > 10 for x in out.split() if x.strip().isdigit()):
            return True
        # NON-INFERENCE WORK. The idle timer only counts requests THROUGH THIS PROXY, and the
        # GPU check only sees inference. A 176 GiB backup, an interactive ssh session, a build
        # -- none of those touch either signal, so a 30-minute transfer would be suspended out
        # from under itself and corrupt the copy. Treat a login session or a live transfer as
        # busy; the cost of a false "busy" is a machine that stays awake, which is recoverable.
        rc, out = await ssh(self.c.host,
            "timeout 10 sh -c \"who | wc -l; pgrep -c -x 'rsync|scp|cp|dd|tar' 2>/dev/null || echo 0\"",
            timeout=15)
        if rc == 0:
            nums = [int(x) for x in out.split() if x.strip().isdigit()]
            if any(n > 0 for n in nums):
                return True
        try:
            async with httpx.AsyncClient(timeout=5) as cl:
                slots = (await cl.get(self.base + "/slots")).json()
            if isinstance(slots, list) and any(s.get("is_processing") for s in slots):
                return True
        except Exception:
            pass
        return False

    async def sleep_node(self) -> None:
        if not self.c.enable_suspend:
            return
        # ALWAYS unload first: /var (24 GiB) cannot hold a 32 GiB VRAM spill.
        log("suspend: stopping llama-server before suspend (VRAM spill would not fit)")
        await ssh(self.c.host, "pkill -x llama-server || true", timeout=30)
        # Wait for the process to EXIT, not a fixed 8 s: with --resume the shutdown saves every slot to disk (41.6 s for
        # a 9.2k-token slot on .73, 2026-09-25), and suspending mid-save loses it. Bounded; SIGKILL only as a last resort.
        rc, _ = await ssh(self.c.host, "for i in $(seq 1 150); do pgrep -x llama-server >/dev/null || exit 0; sleep 2; "
                          "done; pkill -9 -x llama-server; exit 1", timeout=330)
        if rc != 0:
            log("suspend: llama-server did not exit within 300 s -- SIGKILLed (a --resume save may be lost)")
        await asyncio.sleep(2)
        # LAST-MOMENT RE-CHECK. The 8 s unload window is long enough for a request to arrive and
        # for ensure_ready() to begin a load. Suspending on top of that is what broke .73 on
        # 2026-09-19: suspend armed 14:38:55, load started 14:38:56, machine slept 14:39:04 with
        # llama-server mid-load, and the GPU returned in a state where nvidia-smi blocked.
        if time.time() - self.last_request < 10:
            log("suspend: ABORTED -- a request arrived during the unload window")
            self.state = "unknown"
            return
        # NAMED transient unit so a wake can cancel it. An anonymous --on-active timer is armed
        # and uncancellable for its whole delay.
        rc, _ = await ssh(self.c.host,
            "sudo -n systemd-run --unit=apollo-suspend --on-active=2 "
            "--timer-property=AccuracySec=100ms systemctl suspend", timeout=20)
        self.state = "suspended" if rc == 0 else "suspend-failed"
        log(f"suspend: {self.state}")

    # ---- pre-warm: prefill the agent's system prompt + tools so the first message after a cold
    # load does not pay for it. Hermes's head is ~25k tokens, ~3 min of prefill on .73. Measured
    # (data/receipts/split-prefill-73, warm-head probe): a raw warm-up cut EXACTLY at the user-turn
    # boundary gives full reuse on the qwen35 hybrid (8,150/8,150 cached, 2.1 s vs 90.6 s cold).
    # The cut matters: the recurrent layers can only restore at a saved state, and the end of the
    # warm-up prompt is where that state is saved.
    last_warm: dict = {}

    def capture_head(self, body: bytes) -> None:
        """Remember the last agent-shaped head (big system prompt + tools) this proxy forwarded.
        Stored locally only (run/warm_head.json is gitignored): it contains personal memory text."""
        try:
            d = json.loads(body)
            msgs, tools = d.get("messages") or [], d.get("tools") or []
            if not (tools and msgs and msgs[0].get("role") == "system"
                    and isinstance(msgs[0].get("content"), str) and len(msgs[0]["content"]) >= WARM_MIN_CHARS):
                return
            head = {"system": msgs[0]["content"], "tools": tools,
                    "kwargs": {k: d[k] for k in ("chat_template_kwargs", "reasoning_effort") if k in d},
                    "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            # kwargs are part of the key: reasoning_effort renders BEFORE the tools in the Qwen3.8 template, so two
            # clients with different efforts share no prefix at all (observed 09-25: 16k-token head, sim 0.000)
            key = hash((head["system"], json.dumps(tools, sort_keys=True), json.dumps(head["kwargs"], sort_keys=True)))
            if key == getattr(self, "_head_key", None):
                return
            self._head_key = key
            tmp = WARM_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(head, f); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, WARM_FILE)
            log(f"warm: captured head ({len(head['system'])} chars system, {len(tools)} tools, kwargs {head['kwargs']})")
        except Exception as e:
            log(f"warm: capture skipped: {type(e).__name__}: {e}")

    async def warm(self, reason: str) -> dict:
        """Prefill the captured head on the node. Safe to call any time the node is serving."""
        try:
            head = json.load(open(WARM_FILE))
        except (OSError, ValueError):
            self.last_warm = {"ok": False, "reason": reason, "detail": "no captured head yet"}
            return self.last_warm
        system = _redate(head["system"])
        mark = "WARM_USER_CONTENT_MARKER_7f3a"
        self.inflight += 1          # never suspend mid-warm
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=WARM_TIMEOUT) as cl:
                r = await cl.post(self.base + "/apply-template", json={
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": mark}],
                    "tools": head["tools"], **head.get("kwargs", {})})
                rendered = r.json()["prompt"]
                prefix = rendered[:rendered.index(mark)]
                r = await cl.post(self.base + "/completion", json={
                    "prompt": prefix, "n_predict": 1, "temperature": 0, "cache_prompt": True})
                t = r.json().get("timings", {})
            self.last_warm = {"ok": True, "reason": reason, "tokens": t.get("prompt_n"),
                              "cached_already": t.get("cache_n"), "seconds": round(time.time() - t0, 1),
                              "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        except Exception as e:
            self.last_warm = {"ok": False, "reason": reason, "detail": f"{type(e).__name__}: {e}"}
        finally:
            self.inflight -= 1
        log(f"warm: {self.last_warm}")
        return self.last_warm


N = Node(C)
app = FastAPI(title="Apollo wake-on-demand proxy")

@app.on_event("startup")
async def _boot():
    log(f"proxy up — node={C.host} mac={C.mac} idle={C.idle_secs}s suspend={C.enable_suspend}")
    asyncio.create_task(idle_monitor())

async def idle_monitor():
    while True:
        await asyncio.sleep(60)
        try:
            idle = time.time() - N.last_request
            if idle < C.idle_secs or N.state == "suspended":
                continue
            if not await N.reachable():
                N.state = "suspended"; continue
            if await N.busy():
                log(f"idle {idle:.0f}s but node is busy — not suspending")
                N.last_request = time.time()          # reset; work is happening
                continue
            log(f"idle {idle:.0f}s >= {C.idle_secs}s — suspending")
            # Hold the SAME lock ensure_ready() uses. The suspend path previously took no lock,
            # so a wake could begin while a suspend was in flight.
            async with N.lock:
                if time.time() - N.last_request < C.idle_secs:
                    log("suspend: stood down -- a request arrived while acquiring the lock")
                    continue
                await N.sleep_node()
        except Exception as e:                        # a monitor that dies silently is the bug
            log(f"idle_monitor error: {type(e).__name__}: {e}")

@app.get("/status")
async def status():
    try:
        h = json.load(open(WARM_FILE))
        head = {"system_chars": len(h["system"]), "tools": len(h["tools"]), "captured_at": h.get("captured_at")}
    except (OSError, ValueError, KeyError):
        head = None
    return {"node": C.host, "state": N.state, "inflight": N.inflight,
            "idle_seconds": round(time.time() - N.last_request),
            "idle_timeout": C.idle_secs, "serving": await N.serving(),
            "suspend_enabled": C.enable_suspend,
            "warm": {"on_load": WARM_ON_LOAD, "head": head, "last": N.last_warm}}

@app.post("/wake")
async def manual_wake():
    ok, why = await N.ensure_ready()
    return JSONResponse({"ok": ok, "detail": why}, status_code=200 if ok else 503)

@app.post("/warm")
async def manual_warm():
    """Wake if needed, then prefill the captured agent head. Blocks until the prefill is done."""
    ok, why = await N.ensure_ready()
    if not ok:
        return JSONResponse({"ok": False, "detail": why}, status_code=503)
    return await N.warm("manual /warm")

def _warm_after_load(why: str, via: str) -> None:
    """Warm only after a load NO chat request is waiting on (a client's startup probe). If a chat
    triggered the load, it prefills its own head anyway and a warm-up would only queue ahead of it."""
    if WARM_ON_LOAD and why == "woken and loaded":
        asyncio.create_task(N.warm(f"post-load via {via}"))

@app.post("/suspend")
async def manual_suspend():
    if await N.busy():
        return JSONResponse({"ok": False, "detail": "node busy"}, status_code=409)
    await N.sleep_node()
    return {"ok": True, "state": N.state}

@app.post("/keepalive")
async def keepalive():
    """Reset the idle timer WITHOUT waking the node.

    For a client that wants to hold the endpoint open while a user is active (an
    "endpoint keep-alive" toggle) without forcing a wake when they are not. Polling /v1/models
    would also reset the timer, but it calls ensure_ready() and therefore WAKES a sleeping
    machine -- the opposite of what a passive keep-alive should do.
    """
    N.last_request = time.time()
    return {"ok": True, "state": N.state, "woke_anything": False}


@app.get("/health")
async def health():
    """Liveness of the PROXY, and honest about the node. Deliberately does NOT wake:
    a monitoring poll must never spin up a sleeping machine, and a 200 here must not be read
    as "the model is loaded" (that mistake has been made twice -- llama-swap answering /health,
    and /v1/models answering mid-load). Callers wanting the model should just send a request."""
    return JSONResponse({"status": "ok", "proxy": "up",
                         "node": "serving" if await N.serving() else "asleep_or_loading",
                         "note": "proxy is up; the node wakes on a /v1, /props or /slots request"})


@app.api_route("/props", methods=["GET"])
@app.api_route("/slots", methods=["GET"])
async def passthrough(request: Request):
    """Model metadata (n_ctx above all) lives OUTSIDE /v1 on llama.cpp's server. Without these
    routes the proxy 404s them, and a client that cannot read n_ctx falls back to a stale or
    default context length -- which is how a 262144-context server got treated as something
    smaller and the gateway rejected the request for sending truncation parameters
    (observed from hermes-go on mobile, 2026-08-29 10:46, inside the 57 s cold-load window).
    These wake the node, because a client asking for them intends to use the model."""
    ok, why = await N.ensure_ready()
    if not ok:
        return JSONResponse({"error": {"message": f"node unavailable: {why}", "type": "wake_failed"}},
                            status_code=503, headers={"Retry-After": "60"})
    _warm_after_load(why, request.url.path)
    N.inflight += 1
    try:
        async with httpx.AsyncClient(timeout=30) as cl:
            r = await cl.get(f"{N.base}{request.url.path}")
        return JSONResponse(json.loads(r.text) if r.text else {}, status_code=r.status_code)
    finally:
        N.inflight -= 1
        N.last_request = time.time()


@app.api_route("/v1/{path:path}", methods=["GET", "POST"])
async def proxy(path: str, request: Request):
    N.last_request = time.time()
    body = await request.body()
    want_stream = b'"stream": true' in body or b'"stream":true' in body
    url_path = path
    if request.method == "POST" and path == "chat/completions":
        N.capture_head(body)

    if want_stream:
        # Start the response IMMEDIATELY and wake INSIDE the generator, emitting SSE comments
        # while we wait. Otherwise the client sees no bytes for the whole cold start (77-99s
        # measured) and a time-to-first-byte watchdog kills the request before the model ever
        # loads -- hermes-go's default no-byte TTFB cutoff is 120s, which a real prompt's
        # prefill could exceed on top of the load. A ':' line is an SSE comment: ignored by
        # every compliant client, but it is bytes, so TTFB never arms.
        async def gen():
            N.inflight += 1
            try:
                task = asyncio.create_task(N.ensure_ready())
                while not task.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(task), timeout=5)
                    except asyncio.TimeoutError:
                        yield b": waking\n\n"
                ok, why = task.result()
                if not ok:
                    yield ("data: " + json.dumps(
                        {"error": {"message": f"node unavailable: {why}",
                                   "type": "wake_failed"}}) + "\n\n").encode()
                    yield b"data: [DONE]\n\n"
                    return
                async with httpx.AsyncClient(timeout=None) as cl:
                    async with cl.stream(request.method, f"{N.base}/v1/{url_path}",
                            content=body, headers={"Content-Type": "application/json"}) as r:
                        # Keep the keepalive going until the model's FIRST byte, not just until
                        # the node is awake. An image is ~16k prompt tokens and prefills for
                        # ~112 s on 2xP100 at ~143 tok/s, during which llama.cpp emits nothing --
                        # indistinguishable from a hang to the client, which is how a fully
                        # generated 284-token answer got dropped on 2026-08-29.
                        it = r.aiter_raw()

                        async def _next():
                            try:
                                return await it.__anext__()
                            except StopAsyncIteration:
                                return None

                        while True:
                            task = asyncio.ensure_future(_next())
                            while not task.done():
                                try:
                                    await asyncio.wait_for(asyncio.shield(task), timeout=10)
                                except asyncio.TimeoutError:
                                    yield b": processing\n\n"
                            chunk = task.result()
                            if chunk is None:
                                break
                            yield chunk
            finally:
                N.inflight -= 1
                N.last_request = time.time()
        return StreamingResponse(gen(), media_type="text/event-stream")

    ok, why = await N.ensure_ready()
    if not ok:
        return JSONResponse({"error": {"message": f"node unavailable: {why}", "type": "wake_failed"}},
                            status_code=503, headers={"Retry-After": "60"})
    if request.method == "GET":             # e.g. /v1/models at client startup: nothing is queued
        _warm_after_load(why, f"/v1/{path}")
    N.inflight += 1
    try:
        async with httpx.AsyncClient(timeout=None) as cl:
            r = await cl.request(request.method, f"{N.base}/v1/{url_path}", content=body,
                                 headers={"Content-Type": "application/json"})
        return JSONResponse(json.loads(r.text) if r.text else {}, status_code=r.status_code)
    finally:
        N.inflight -= 1
        N.last_request = time.time()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("WP_PORT", "8099")))
