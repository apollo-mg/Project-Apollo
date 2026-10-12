#!/usr/bin/env python3
"""Render-only gate for the Turbo-Brilliance pelican test (no generation).

Starts llama-server with run_ladder.py's exact flags on the stock IQ3_M, once with the GGUF's own template and once
with DavidAU's pinned template (--chat-template-file), and asks the server's own /apply-template to render the pelican
request untagged and with each candidate {REASON:mode} tag. Checks, written before looking:
  G1  every tagged render contains its mode's system block (a 160-char slice from the middle of it) and no '{REASON:'
  G2  the untagged render under DavidAU's template is byte-identical to the stock template's untagged render
  G3  the stock untagged render equals svgbench-pelican3/prompt_BASE_r1.txt (same weights, older binary)
Writes render_check/*.txt and render_check/summary.json.
  render_check.py"""
import hashlib, json, os, re, signal, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
HERE = ROOT / "data/receipts/svgbench-turbobrilliance"
OUT = HERE / "render_check"
SERVER = ROOT / "engines/buun-llama-cpp/build_rocm/bin/llama-server"
MODEL = "/mnt/TG_2TB/AI/Models/pelican3/Qwen3.8-27B.i1-IQ3_M.gguf"
TPL = HERE / "templates/turbo_brilliance_cbb40c02.jinja"
TASK = "Generate an SVG of a pelican riding a bicycle."
MODES = {"coder": "system_instruction_coder_DAU", "quinn": "system_instruction_quinn_DAU",
         "omni": "system_instruction_DAU", "ultra": "system_instruction_xxhigh_DAU"}
FLAGS = ["-ngl", "99", "-c", "24576", "-np", "1", "-fa", "on", "--kv-unified", "-ctk", "q8_0", "-ctv", "q8_0",
         "-n", "20000", "--reasoning-effort", "medium", "--min-p", "0", "--jinja", "--host", "127.0.0.1", "--port", "8090"]


def call(path, body=None, timeout=30):
    req = urllib.request.Request(f"http://127.0.0.1:8090{path}", data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def serve(extra, log):
    p = subprocess.Popen([str(SERVER), "-m", MODEL, *FLAGS, *extra], stdout=open(log, "w"), stderr=subprocess.STDOUT,
                         start_new_session=True)
    (OUT / f"{log.stem}.pid").write_text(str(p.pid))
    for _ in range(150):
        if p.poll() is not None:
            sys.exit(f"server exited early, see {log}")
        try:
            if call("/health", timeout=5).get("status") == "ok":
                return p
        except Exception:
            pass
        time.sleep(2)
    stop(p)
    sys.exit("server never ready")


def stop(p):
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        p.wait(40)
    except ProcessLookupError:
        pass
    time.sleep(3)


def render(name, content):
    prompt = call("/apply-template", {"messages": [{"role": "user", "content": content}]})["prompt"]
    (OUT / f"{name}.txt").write_text(prompt)
    return prompt


def block(var):
    t = TPL.read_text()
    m = re.search(r"\{%-?\s*set " + var + r"\s*-?%\}(.*?)\{%-?\s*endset\s*-?%\}", t, re.S)
    return m.group(1) if m else None


OUT.mkdir(parents=True, exist_ok=True)
res = {"template_sha256": hashlib.sha256(TPL.read_bytes()).hexdigest(), "server": str(SERVER), "model": MODEL}

p = serve([], OUT / "server_stock.log")
try:
    stock = render("stock_untagged", TASK)
finally:
    stop(p)

p = serve(["--chat-template-file", str(TPL)], OUT / "server_tb.log")
try:
    tb = {"untagged": render("tb_untagged", TASK)}
    for m in MODES:
        tb[m] = render(f"tb_{m}", "{REASON:" + m + "} " + TASK)
finally:
    stop(p)

g1 = {}
for m, var in MODES.items():
    b = (block(var) or "").strip()
    mid = b[len(b) // 2: len(b) // 2 + 160]
    g1[m] = {"block_chars": len(b), "slice_found": bool(mid) and mid in tb[m], "tag_absent": "{REASON:" not in tb[m],
             "task_present": TASK in tb[m], "render_chars": len(tb[m]),
             "render_sha256": hashlib.sha256(tb[m].encode()).hexdigest()}
old = (ROOT / "data/receipts/svgbench-pelican3/prompt_BASE_r1.txt").read_text()
res.update(
    G1=g1, G1_pass=all(v["slice_found"] and v["tag_absent"] and v["task_present"] for v in g1.values()),
    G2_pass=tb["untagged"] == stock, G3_pass=stock == old,
    stock_untagged={"chars": len(stock), "sha256": hashlib.sha256(stock.encode()).hexdigest(), "repr": stock},
    tb_untagged={"chars": len(tb["untagged"]), "sha256": hashlib.sha256(tb["untagged"].encode()).hexdigest(),
                 "repr_head": tb["untagged"][:400], "repr_tail": tb["untagged"][-200:]},
)
(OUT / "summary.json").write_text(json.dumps(res, indent=1))
print(json.dumps({k: v for k, v in res.items() if k not in ("stock_untagged", "tb_untagged")}, indent=1))
print("stock untagged:", repr(stock))
print("tb untagged head:", repr(tb["untagged"][:300]))
