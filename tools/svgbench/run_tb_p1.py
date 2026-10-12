#!/usr/bin/env python3
"""One first drawing for one Turbo-Brilliance arm: stock Qwen3.8-27B IQ3_M weights, DavidAU's pinned chat template,
and the pelican request with or without a {REASON:mode} tag. The tag is the only thing that differs between arms.

Used for data/receipts/svgbench-turbobrilliance/PREREG_TURBOBRILLIANCE_PELICAN.md. Same as run_one_p1.py except:
- **Every arm loads DavidAU's template** with --chat-template-file (sha256 pinned below).
- **The request carries the arm's tag.** The meta record renders the tagged request with the server's own
  /apply-template, and the rep is refused before generation (rule R4) unless that render's sha256 equals the one
  render_check.py recorded for the arm.

Usage: run_tb_p1.py ARM REP      (ARM = CTRL | CODER | QUINN | OMNI)
"""
import hashlib, json, subprocess, sys, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_ladder as R  # noqa: E402

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
OUT = ROOT / "data/receipts/svgbench-turbobrilliance"
MODEL = "/mnt/TG_2TB/AI/Models/pelican3/Qwen3.8-27B.i1-IQ3_M.gguf"
TPL = OUT / "templates/turbo_brilliance_cbb40c02.jinja"
TPL_SHA = "e5b216667a07964c3855d43fa0a7fa22bc4894c0a3182851c2ec6a04141572fb"
ARMS = {"CTRL": "", "CODER": "{REASON:coder} ", "QUINN": "{REASON:quinn} ", "OMNI": "{REASON:omni} "}
GEN_CAP_S = 480

_post = R.post
R.post = lambda body, timeout=GEN_CAP_S: _post(body, min(timeout, GEN_CAP_S))
CURRENT = {}                         # arm and rep of the rep in progress, for the reasoning file names


def generate_stream(prompt):
    """run_ladder.generate's request and return value, streamed (prereg Deviation 1) so the reasoning text is kept,
    including the partial text of a rep that hits the 480 s cap. Sampling and server settings are unchanged."""
    import re
    t0 = time.time()
    body = {"model": "x", "temperature": R.TEMP, "max_tokens": R.MAXTOK, "stream": True,
            "stream_options": {"include_usage": True}, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("http://127.0.0.1:8090/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    content, reasoning, finish, usage, timings, chunks, capped = [], [], None, {}, {}, 0, False
    with urllib.request.urlopen(req, timeout=60) as resp:
        for raw in resp:
            if time.time() - t0 > GEN_CAP_S:
                capped = True
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            o = json.loads(data)
            usage = o.get("usage") or usage
            timings = o.get("timings") or timings
            for ch in o.get("choices") or []:
                d = ch.get("delta") or {}
                if d.get("content"):
                    content.append(d["content"])
                if d.get("reasoning_content"):
                    reasoning.append(d["reasoning_content"])
                if d.get("content") or d.get("reasoning_content"):
                    chunks += 1
                finish = ch.get("finish_reason") or finish
    content, reasoning = "".join(content), "".join(reasoning)
    b = R.base(CURRENT["arm"], CURRENT["rep"], "p1")
    if capped:
        Path(b + ".partial_reasoning.txt").write_text(reasoning)
        Path(b + ".partial_content.txt").write_text(content)
        R.record({"quant": CURRENT["arm"], "rep": CURRENT["rep"], "step": "partial", "ts": time.time(),
                  "chunks": chunks, "reasoning_chars": len(reasoning), "content_chars": len(content)})
        raise TimeoutError(f"timed out (stream cap {GEN_CAP_S} s)")
    Path(b + ".reasoning.txt").write_text(reasoning)
    svgs = re.findall(r"<svg.*?</svg>", content, re.S | re.I)
    return {"content": content, "svg": svgs[-1] if svgs else None, "finish": finish,
            "tokens": usage.get("completion_tokens", timings.get("predicted_n")),
            "prompt_tokens": usage.get("prompt_tokens", timings.get("prompt_n")),
            "reasoning_chars": len(reasoning), "elapsed_s": round(time.time() - t0, 1)}


R.generate = generate_stream


def start_server(model, log_path):
    """run_ladder.start_server's flags unchanged, plus the pinned template."""
    log = open(log_path, "w")
    p = subprocess.Popen([str(R.SERVER), "-m", model, "-ngl", "99", "-c", str(R.CTX), "-np", "1",
                          "-fa", "on", "--kv-unified", "-ctk", "q8_0", "-ctv", "q8_0",
                          "-n", str(R.MAXTOK), "--reasoning-effort", "medium", "--min-p", "0",
                          "--jinja", "--chat-template-file", str(TPL), "--host", "127.0.0.1", "--port", "8090"],
                         stdout=log, stderr=log, start_new_session=True)
    for _ in range(120):
        if p.poll() is not None:
            return p, False
        try:
            R.post({"model": "x", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}, 10)
            return p, True
        except Exception:
            time.sleep(2)
    return p, False


def get_json(path, body=None, timeout=15):
    req = urllib.request.Request(f"http://127.0.0.1:8090{path}",
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def expected_sha(arm):
    s = json.loads((OUT / "render_check/summary.json").read_text())
    return s["stock_untagged"]["sha256"] if arm == "CTRL" else s["G1"][arm.lower()]["render_sha256"]


def meta(arm, rep, prompt):
    rec = {"quant": arm, "rep": rep, "step": "meta", "ts": time.time(), "template_sha256": TPL_SHA}
    try:
        rendered = get_json("/apply-template", {"messages": [{"role": "user", "content": prompt}]})["prompt"]
        (OUT / f"prompt_{arm}_r{rep}.txt").write_text(rendered)
        sha = hashlib.sha256(rendered.encode()).hexdigest()
        rec.update(prompt_sha256=sha, prompt_chars=len(rendered), prompt_ok=sha == expected_sha(arm))
    except Exception as e:
        rec.update(prompt_error=repr(e)[:200], prompt_ok=False)
    try:
        s = get_json("/slots")
        rec["kv_bpv"] = s[0].get("kv_bpv") if isinstance(s, list) and s else None
    except Exception as e:
        rec["slots_error"] = repr(e)[:200]
    R.record(rec)
    return rec


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ARMS:
        sys.exit(__doc__)
    arm, rep = sys.argv[1], int(sys.argv[2])
    if hashlib.sha256(TPL.read_bytes()).hexdigest() != TPL_SHA:
        sys.exit("template sha256 mismatch")
    R.OUT = OUT
    prompt = ARMS[arm] + R.TASK
    if R.last(arm, rep, "p1") is not None:
        print(f"{arm} r{rep} is already recorded; nothing to do", flush=True)
        return
    if not R.wait_for_memory(f"{arm} rep {rep}"):
        R.record({"quant": arm, "rep": rep, "step": "server",
                  "error": f"skipped: MemAvailable never reached {R.MEM_START_GB} GB", "ts": time.time()})
        return
    print(f"{time.strftime('%H:%M:%S')} === {arm} rep {rep} ===", flush=True)
    p, ok = start_server(MODEL, OUT / f"server_{arm}_r{rep}.log")
    if not ok:
        R.record({"quant": arm, "rep": rep, "step": "server", "error": "server never ready", "ts": time.time()})
        R.stop_server(p)
        R.cooldown()
        return
    wd = R.MemWatchdog(p)
    wd.start()
    generating = False
    try:
        m = meta(arm, rep, prompt)
        print(f"  prompt {m.get('prompt_chars')} chars | sha {str(m.get('prompt_sha256'))[:12]} | "
              f"ok {m.get('prompt_ok')} | kv_bpv {m.get('kv_bpv')}", flush=True)
        if not m.get("prompt_ok"):
            R.record({"quant": arm, "rep": rep, "step": "invalid", "ts": time.time(),
                      "error": "R4: rendered prompt differs from render_check; not generated"})
            return
        generating = True
        CURRENT.update(arm=arm, rep=rep)
        R.do_step(arm, rep, "p1", prompt, None)
    except KeyboardInterrupt:
        if generating:               # R1: the wall-clock backstop fired mid-generation -- recorded, not rerun
            R.record({"quant": arm, "rep": rep, "step": "p1", "ts": time.time(),
                      "error": "wall-clock backstop (SIGINT) during generation"})
        raise
    finally:
        wd.halt.set()
        R.stop_server(p)
        if wd.tripped:
            R.record({"quant": arm, "rep": rep, "step": "watchdog", "ts": time.time(),
                      "error": f"memory watchdog SIGKILLed the server: MemAvailable < {R.MEM_FLOOR_GB} GB"})
        R.cooldown()
    r = R.last(arm, rep, "p1") or {}
    print(f"{time.strftime('%H:%M:%S')}   {arm} r{rep}: tokens {r.get('tokens')}, prompt tokens "
          f"{r.get('prompt_tokens')}, score {r.get('score')}/{r.get('max')}, reasoning chars "
          f"{r.get('reasoning_chars')}, finish {r.get('finish')}, elapsed {r.get('elapsed_s')}s"
          f"{', ERROR ' + r['error'] if r.get('error') else ''}", flush=True)


if __name__ == "__main__":
    main()
