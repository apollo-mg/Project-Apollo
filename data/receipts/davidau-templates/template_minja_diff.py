#!/usr/bin/env python3
"""Driver for PREREG_TEMPLATE_MINJA_DIFF.md: render the same conversations through llama.cpp's minja
and through Python jinja2, and diff them exactly.

Usage:  template_minja_diff.py <template.jinja> [more.jinja ...]
"""
import json, os, signal, subprocess, sys, time, urllib.request

BIN = "/mnt/TG_2TB/Projects/buun-da458/build_rocm/bin/llama-server"
MODEL = "/mnt/TG_2TB/AI/Models/exl3/Qwen3-0.6B-exl3-4.0bpw"
PORT = 8196
H = f"http://127.0.0.1:{PORT}"
OUT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(OUT, "results.jsonl")

TOOLS = [{"type": "function", "function": {
    "name": "get_weather", "description": "Get the weather for a city",
    "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}]

CASES = {
    "1_plain": {"messages": [{"role": "system", "content": "You are terse."},
                             {"role": "user", "content": "Hello."}]},
    "2_tools": {"messages": [{"role": "user", "content": "Weather in Chengdu?"}], "tools": TOOLS},
    "3_args_string": {"messages": [
        {"role": "user", "content": "Weather in Chengdu?"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "get_weather", "arguments": "{\"city\": \"Chengdu\"}"}}]}], "tools": TOOLS},
    "4_args_object": {"messages": [
        {"role": "user", "content": "Weather in Chengdu?"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "get_weather", "arguments": {"city": "Chengdu"}}}]}], "tools": TOOLS},
    "5_round_trip": {"messages": [
        {"role": "user", "content": "Weather in Chengdu?"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "get_weather", "arguments": "{\"city\": \"Chengdu\"}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "22C, clear"},
        {"role": "assistant", "content": "It's 22C and clear."},
        {"role": "user", "content": "And tomorrow?"}], "tools": TOOLS},
    "6_reason_tag": {"messages": [{"role": "user", "content": "{REASON:einstein} Invent a better kettle."}]},
}


def emit(row):
    row["ts"] = time.strftime("%F %T")
    with open(RES, "a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())


def start(template):
    p = subprocess.Popen([BIN, "-m", MODEL, "--chat-template-file", template, "-ngl", "99",
                          "-c", "4096", "-np", "1", "--jinja", "--host", "127.0.0.1", "--port", str(PORT)],
                         stdout=open(os.path.join(OUT, "server.log"), "w"), stderr=subprocess.STDOUT,
                         start_new_session=True)
    for _ in range(120):
        if p.poll() is not None:
            raise SystemExit(f"server exited rc={p.returncode}; see server.log")
        try:
            urllib.request.urlopen(H + "/health", timeout=3)
            return p
        except Exception:
            time.sleep(2)
    raise SystemExit("server never became healthy")


def stop(p):
    if p.poll() is None:
        os.killpg(p.pid, signal.SIGTERM)
        try:
            p.wait(20)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
    time.sleep(2)


def minja_render(body):
    req = urllib.request.Request(H + "/apply-template", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("prompt")


def jinja2_render(text, body):
    import jinja2
    # transformers renders chat templates with trim_blocks and lstrip_blocks ON; matching it matters,
    # otherwise every comparison differs by whitespace alone.
    env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True,
                             undefined=jinja2.ChainableUndefined, extensions=["jinja2.ext.loopcontrols"])
    env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}
    env.filters["tojson"] = lambda v, **kw: json.dumps(v, ensure_ascii=False)
    tpl = env.from_string(text)
    return tpl.render(messages=body["messages"], tools=body.get("tools"), add_generation_prompt=True,
                      bos_token="", eos_token="<|im_end|>", **body.get("chat_template_kwargs", {}))


def first_diff(a, b):
    la, lb = (a or "").splitlines(), (b or "").splitlines()
    for i in range(max(len(la), len(lb))):
        x = la[i] if i < len(la) else "<missing>"
        y = lb[i] if i < len(lb) else "<missing>"
        if x != y:
            return i + 1, x, y
    return None, None, None


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for template in sys.argv[1:]:
        name = os.path.basename(template)
        text = open(template, encoding="utf-8").read()
        print(f"\n=== {name}")
        p = start(template)
        try:
            for case, body in CASES.items():
                m = j = None
                m_err = j_err = None
                try:
                    m = minja_render(body)
                except urllib.error.HTTPError as e:          # the body says what it objected to
                    m_err = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"
                except Exception as e:
                    m_err = repr(e)
                try:
                    j = jinja2_render(text, body)
                except Exception as e:
                    j_err = repr(e)
                same = (m is not None and j is not None and m == j)
                line, mx, jx = first_diff(m, j) if (m and j) else (None, None, None)
                emit({"template": name, "case": case, "identical": same, "minja_error": m_err,
                      "jinja2_error": j_err, "minja_len": len(m or ""), "jinja2_len": len(j or ""),
                      "first_diff_line": line, "minja_line": (mx or "")[:300], "jinja2_line": (jx or "")[:300],
                      "minja_prompt": (m or "")[:4000]})
                status = "IDENTICAL" if same else ("minja ERROR" if m_err else "jinja2 ERROR" if j_err else f"DIFFER at line {line}")
                print(f"  {case:16s} {status}  (minja {len(m or '')} B, jinja2 {len(j or '')} B)")
                if not same and line:
                    print(f"      minja : {(mx or '')[:150]}")
                    print(f"      jinja2: {(jx or '')[:150]}")
                if m_err:
                    print(f"      minja error: {m_err[:200]}")
                if j_err:
                    print(f"      jinja2 error: {j_err[:200]}")
        finally:
            stop(p)


if __name__ == "__main__":
    main()
