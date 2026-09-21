#!/usr/bin/env python3
"""Argus ACP probe — establish, empirically, what an agent under test actually does.

Written because `stub_agent.py` was built against POST /api/sessions/{id}/chat, a route that
exists in no Hermes codebase. This talks to the real binary and records observed bytes.

It also answers the question that decides Argus's whole architecture for a given agent:

  Does the agent DELEGATE execution to the client (ACP `terminal/create`, `fs/write_text_file`)?
    yes -> Argus IS the environment. Full observability by protocol, no instrumentation, and
           this is the seam where a world model could serve the responses.
    no  -> the agent runs commands in its own process. Argus must instrument the agent side
           (the fake-google skill + audit log) and observe intent via session/update.

hermes-go @ 869e56ec is the SECOND kind -- grep shows acp_adapter never calls create_terminal
or the client fs methods. Do not assume; this probe re-checks per agent, because that is the
point of a harness meant for arbitrary software.

Run:  .venv/bin/python acp_probe.py --agent-cwd /mnt/TG_2TB/AI/hermes-go
"""
import argparse, asyncio, json, os, sys, time
from pathlib import Path
import acp

DELEGATION_METHODS = {"create_terminal", "terminal_output", "wait_for_terminal_exit",
                      "kill_terminal", "release_terminal", "read_text_file", "write_text_file"}

class ProbeClient(acp.Client):
    """Implements every client method and records which ones the agent actually invokes."""
    def __init__(self, sink, allow=False):
        self.sink, self.calls, self.updates = sink, [], []
        self.allow = allow

    def _log(self, kind, name, payload):
        rec = {"t": round(time.time(), 3), "kind": kind, "name": name, "payload": payload}
        self.sink.write(json.dumps(rec, default=str) + "\n"); self.sink.flush()
        os.fsync(self.sink.fileno())          # standing rule: persist per item
        (self.updates if kind == "update" else self.calls).append(rec)

    async def session_update(self, session_id, update, **kw):
        self._log("update", type(update).__name__, getattr(update, "model_dump", lambda: update)())

    async def request_permission(self, options, session_id, tool_call, **kw):
        opts = [getattr(o, "model_dump", lambda: o)() for o in options]
        self._log("call", "request_permission",
                  {"tool_call": getattr(tool_call, "model_dump", lambda: tool_call)(),
                   "options": opts, "answered": "allow" if self.allow else "deny"})
        # DENY BY DEFAULT. Hermes runs commands in its OWN process on this machine --
        # acp_adapter never calls the client-side terminal, so "allow" is a real
        # subprocess here, not a simulated one. --allow-tools is the explicit opt-in.
        import acp.schema as sch
        want = "allow" if self.allow else "reject"   # ACP denies by SELECTING a reject option
        pick = next((o for o in opts if str(o.get("kind", "")).startswith(want)), None)
        if pick is None:
            return sch.RequestPermissionResponse(outcome=sch.DeniedOutcome(outcome="cancelled"))
        # AllowedOutcome is misnamed: it means "an option was SELECTED", and that option may
        # be a reject_* one. It is also the only variant carrying the 'outcome' discriminator.
        return sch.RequestPermissionResponse(
            outcome=sch.AllowedOutcome(outcome="selected", option_id=pick["option_id"]))

    # --- delegation surface: if any of these fire, Argus can BE the environment ---
    async def create_terminal(self, command, session_id, args=None, cwd=None, env=None,
                              output_byte_limit=None, **kw):
        self._log("call", "create_terminal", {"command": command, "args": args, "cwd": cwd})
        raise NotImplementedError
    async def terminal_output(self, session_id, terminal_id, **kw):
        self._log("call", "terminal_output", {"terminal_id": terminal_id}); raise NotImplementedError
    async def wait_for_terminal_exit(self, session_id, terminal_id, **kw):
        self._log("call", "wait_for_terminal_exit", {"terminal_id": terminal_id}); raise NotImplementedError
    async def kill_terminal(self, session_id, terminal_id, **kw):
        self._log("call", "kill_terminal", {"terminal_id": terminal_id}); raise NotImplementedError
    async def release_terminal(self, session_id, terminal_id, **kw):
        self._log("call", "release_terminal", {"terminal_id": terminal_id}); raise NotImplementedError
    async def read_text_file(self, path, session_id, limit=None, line=None, **kw):
        self._log("call", "read_text_file", {"path": path}); raise NotImplementedError
    async def write_text_file(self, content, path, session_id, **kw):
        self._log("call", "write_text_file", {"path": path, "bytes": len(content or "")})
        raise NotImplementedError

    async def ext_method(self, method, params):
        self._log("call", "ext_method", {"method": method}); return {}
    async def ext_notification(self, method, params):
        self._log("call", "ext_notification", {"method": method})
    def on_connect(self, conn): pass   # called synchronously by ClientSideConnection


async def main(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    errf = open(out / "agent_stderr.log", "w")
    with open(out / "acp_trace.jsonl", "w") as sink:
        client = ProbeClient(sink, allow=a.allow_tools)
        proc = await asyncio.create_subprocess_exec(
            a.python, "-m", "acp_adapter.entry",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=errf, cwd=a.agent_cwd,
            env={**os.environ, "HERMES_HOME": str(Path(a.hermes_home).resolve())})
        # NB: input_stream = agent stdin (StreamWriter), output_stream = agent stdout (StreamReader)
        conn = acp.connect_to_agent(client, proc.stdin, proc.stdout)
        try:
            init = await asyncio.wait_for(conn.initialize(
                protocol_version=acp.PROTOCOL_VERSION,
                client_info=acp.schema.Implementation(name="argus-probe", version="0")), a.timeout)
            d = init.model_dump() if hasattr(init, "model_dump") else init
            print(json.dumps(d, indent=2, default=str))
            sink.write(json.dumps({"kind": "initialize", "payload": d}, default=str) + "\n")

            if a.prompt:
                sandbox = Path(a.sandbox).resolve(); sandbox.mkdir(parents=True, exist_ok=True)
                sess = await asyncio.wait_for(conn.new_session(cwd=str(sandbox)), a.timeout)
                sid = sess.session_id
                print(f"\nsession {sid}  cwd={sandbox}\nprompting...\n", flush=True)
                import acp.schema as sch
                pr = await asyncio.wait_for(conn.prompt(
                    prompt=[sch.TextContentBlock(type="text", text=a.prompt)],
                    session_id=sid), a.prompt_timeout)
                print(f"stop_reason: {getattr(pr, 'stop_reason', pr)}")
        except Exception as e:
            print(f"initialize FAILED: {type(e).__name__}: {e}", file=sys.stderr)
            print(f"--- agent stderr: {out/'agent_stderr.log'}", file=sys.stderr)
            raise
        finally:
            proc.terminate()
            try: await asyncio.wait_for(proc.wait(), 5)
            except asyncio.TimeoutError: proc.kill()
            errf.close()
    fired = {c["name"] for c in client.calls} & DELEGATION_METHODS
    print(f"\ndelegation methods invoked: {sorted(fired) or 'none -- agent executes in its own process'}")
    from collections import Counter
    print("session/update events:", dict(Counter(u["name"] for u in client.updates)) or "none")
    print("client calls:", dict(Counter(c["name"] for c in client.calls)) or "none")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--agent-cwd", default="/mnt/TG_2TB/AI/hermes-go")
    p.add_argument("--python", default="/mnt/TG_2TB/AI/hermes-go/.venv/bin/python")
    p.add_argument("--out", default="runs/probe")
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument("--prompt", default=None, help="send a real prompt turn after initialize")
    p.add_argument("--prompt-timeout", type=float, default=900.0)
    p.add_argument("--hermes-home", default="agent-home",
                   help="isolated HERMES_HOME for the agent under test")
    p.add_argument("--sandbox", default="runs/sandbox", help="cwd handed to the agent session")
    p.add_argument("--allow-tools", action="store_true",
                   help="answer permission requests with ALLOW (runs real commands)")
    asyncio.run(main(p.parse_args()))
