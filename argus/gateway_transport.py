#!/usr/bin/env python3
"""Gateway transport for Argus — the interface Tom's fork actually exposes.

WHY THIS EXISTS: the ACP adapter is upstream Hermes and stdio-only; the mobile app never
touches it. Tom's work is apps/mobile/** plus tui_gateway, and mobile talks to
gateway/platforms/api_server.py over REST. Testing the fork means testing this surface.

MUST USE /chat/stream, NOT /chat. The synchronous endpoint returns only
{role, content} -- no tool information at all (verified against a live turn). Argus's
SUSPECT verdict counts tool calls, so the sync endpoint would silently make every honest
agent look like a liar. The SSE endpoint emits, per api_server.py:3954:

    tool.started   {message_id, tool_name, preview, args}   <-- args ARE included
    tool.completed {message_id, tool_name, preview, args}
    tool.failed    ...
    assistant.delta / assistant.completed, message.started
    run.started / run.completed / run.failed / run.cancelled
    tool.progress  (also carries reasoning under tool_name "_thinking")

That is BETTER evidence than ACP gives: ACP's ToolCallStart hardcodes raw_input=None
(acp_adapter/tools.py:1044) and puts the command in a prose title. Here the arguments
arrive structured.
"""
import json, time, urllib.request, urllib.error

class GatewayError(RuntimeError): pass

def _req(base, path, key, body=None, method="POST", timeout=900, stream=False):
    r = urllib.request.Request(
        base.rstrip("/") + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}",
                 **({"Accept": "text/event-stream"} if stream else {})})
    return urllib.request.urlopen(r, timeout=timeout)

def new_session(base, key, title, model=None):
    """Create a gateway session, optionally PINNED to a model.

    Without `model` the session inherits whatever endpoint the Hermes UI is currently
    pointed at (the session object comes back with "model": null). That is an
    instrument-version hazard sitting inside the harness: the same scenario run weeks
    apart can silently execute on different hardware and a different model, and nothing
    in the results records which. Mark switches this endpoint by hand between the P100
    node and the 9070. Pin it.
    """
    body = {"title": title}
    if model is not None:
        body["model"] = model
    with _req(base, "/api/sessions", key, body, timeout=60) as f:
        d = json.loads(f.read())
    # Response nests under "session" -- {"object":"hermes.session","session":{"id":...}}.
    # A flat d["id"] read (what the pre-ACP stub assumed) returns None here.
    sid = (d.get("session") or {}).get("id") or d.get("session_id") or d.get("id")
    if not sid: raise GatewayError(f"no session id in response: {str(d)[:200]}")
    return sid

def chat_stream(base, key, sid, message, timeout=900, on_event=None, seed=None):
    """One turn over SSE. Returns (text, tool_calls, run_failed_reason).

    WALL-CLOCK DEADLINE, not just a socket timeout. urllib's `timeout` applies per socket
    operation, so an SSE stream that keeps trickling bytes NEVER trips it however long the
    turn runs. Observed: a calibration scenario ran 6,827s under a nominal --timeout 1200,
    and single scenarios consumed entire 2-hour passes. The deadline below is checked per
    line, so a slow-but-alive stream is still bounded.
    """
    text, tools, failed = [], [], None
    deadline = time.time() + timeout
    # `seed` is forwarded only if the caller asks for one. Whether the gateway HONOURS
    # it is a separate question -- hermes-agent holds the sampling config, so an unknown
    # field may be silently dropped. probe_gateway_seed.py settles it; do not assume
    # paired seeds work because this field exists.
    _body = {"message": message}
    if seed is not None:
        _body["seed"] = seed
    with _req(base, f"/api/sessions/{sid}/chat/stream", key,
              _body, timeout=timeout, stream=True) as f:
        event = None
        for raw in f:
            if time.time() > deadline:
                failed = f"wall-clock deadline {timeout}s exceeded (stream still open)"
                break
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("event:"):
                event = line[6:].strip(); continue
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]": break
            try: d = json.loads(payload)
            except json.JSONDecodeError: continue
            name = event or d.get("event") or ""
            if on_event: on_event(name, d)
            if name.endswith("assistant.delta") or name == "delta":
                text.append(d.get("delta") or "")
            elif name.endswith("assistant.completed"):
                if d.get("content"): text = [d["content"]]
            elif name.endswith("tool.started"):
                tools.append({"name": d.get("tool_name") or d.get("tool"),
                              "args": d.get("args"), "preview": d.get("preview")})
            elif name.endswith("run.failed") or name == "error":
                failed = str(d)[:300]
            event = None
    return "".join(text), tools, failed
