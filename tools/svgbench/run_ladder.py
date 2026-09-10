#!/usr/bin/env python3
"""svgbench ladder: bit depth x review framing, cost-to-converge.

Pre-registered in data/receipts/svgbench-ladder/PREREG_BITDEPTH_FEEDBACK.md.
One JSON line per generation (flush+fsync); resumes from results.jsonl if interrupted.
Servers are started and stopped by process group from our own Popen -- never by name (AFM-37).
"""
import argparse, json, os, re, signal, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
OUT = ROOT / "data/receipts/svgbench-ladder"
PROBE = ROOT / "tools/svgbench/svg_probe.py"
SERVER = ROOT / "engines/buun-llama-cpp/build_rocm/bin/llama-server"
CTX, MAXTOK, TEMP, REPS = 24576, 20000, 1.0, 3
QUANTS = [
    ("UD-Q2_K_XL", "/mnt/TG_2TB/AI/Models/Qwen3.8-27B-UD-Q2_K_XL.gguf"),
    ("UD-IQ2_M",   "/mnt/TG_2TB/AI/Models/Qwen3.8-27B-UD-IQ2_M.gguf"),
    ("UD-IQ4_XS",  "/mnt/TG_2TB/AI/Models/unsloth-v3/Qwen3.8-27B-UD-IQ4_XS.gguf"),
    ("UD-Q4_K_M",  "/mnt/TG_2TB/AI/Models/unsloth-v3/Qwen3.8-27B-UD-Q4_K_M.gguf"),
]
TASK = "Generate an SVG of a pelican riding a bicycle."
# The ONLY difference between arms. Every other word of the scaffold is shared.
CLAUSE = {
    "intent": "Compare the rendering to what you intended.",
    "goal": "Judge the rendering as a picture of a pelican riding a bicycle.",
}


def scaffold(svg, grid, framing):
    return (f'You were asked: "{TASK}" This is the SVG you produced:\n\n'
            f"```svg\n{svg}\n```\n\n"
            "This is how it renders. Each character is one cell of a 64x30 grid over the image; "
            "' ' is empty and '.:-=+*#%@' run from light to dense:\n\n"
            f"```\n{grid}\n```\n\n"
            f"{CLAUSE[framing]} List its faults briefly (or write \"none\"), "
            "then output a complete corrected SVG.")


def probe(svg_path, png_path):
    r = subprocess.run([sys.executable, str(PROBE), str(svg_path), "--png", str(png_path),
                        "--cols", "64", "--rows", "30"], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"score": 0, "max": None, "checks": None, "grid": "",
                "notes": {"probe_error": r.stderr[-300:]}}


def gpu_snapshot():
    def q(args, pat):
        o = subprocess.run(["rocm-smi"] + args, capture_output=True, text=True).stdout
        m = re.search(pat, o)
        return m.group(1) if m else None
    return {"junction_c": q(["--showtemp"], r"(?i)junction.*?:\s*([0-9.]+)"),
            "sclk_mhz": q(["--showclocks"], r"sclk.*?\((\d+)Mhz\)"),
            "power_w": q(["--showpower"], r"Average Graphics Package Power \(W\):\s*([0-9.]+)")}


def post(body, timeout=1800):
    r = urllib.request.Request("http://127.0.0.1:8090/v1/chat/completions",
                               data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.load(resp)


def start_server(model, log_path):
    log = open(log_path, "w")
    p = subprocess.Popen([str(SERVER), "-m", model, "-ngl", "99", "-c", str(CTX), "-np", "1",
                          "-fa", "on", "--kv-unified", "-ctk", "q8_0", "-ctv", "q8_0",
                          "-n", str(MAXTOK), "--reasoning-effort", "medium", "--min-p", "0",
                          "--jinja", "--host", "127.0.0.1", "--port", "8090"],
                         stdout=log, stderr=log, start_new_session=True)
    for _ in range(120):
        if p.poll() is not None:
            return p, False
        try:
            post({"model": "x", "messages": [{"role": "user", "content": "hi"}],
                  "max_tokens": 1}, 10)
            return p, True
        except Exception:
            time.sleep(2)
    return p, False


def stop_server(p):
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        p.wait(40)
    except Exception:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
    time.sleep(3)


def generate(prompt):
    t0 = time.time()
    o = post({"model": "x", "temperature": TEMP, "max_tokens": MAXTOK,
              "messages": [{"role": "user", "content": prompt}]})
    ch = o["choices"][0]
    m = ch["message"]
    content = m.get("content") or ""
    svgs = re.findall(r"<svg.*?</svg>", content, re.S | re.I)
    u = o.get("usage") or {}
    return {"content": content, "svg": svgs[-1] if svgs else None,
            "finish": ch.get("finish_reason"), "tokens": u.get("completion_tokens"),
            "prompt_tokens": u.get("prompt_tokens"),
            "reasoning_chars": len(m.get("reasoning_content") or ""),
            "elapsed_s": round(time.time() - t0, 1)}


def record(rec):
    with open(OUT / "results.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
        f.flush()
        os.fsync(f.fileno())


def records():
    p = OUT / "results.jsonl"
    if not p.exists():
        return []
    out = []
    for line in open(p):
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def base(quant, rep, step):
    return str(OUT / f"{quant}_r{rep}_{step}")


def load(quant, rep, step, ext):
    f = Path(base(quant, rep, step) + ext)
    return f.read_text() if f.exists() else None


def last(quant, rep, step):
    hits = [r for r in records() if (r.get("quant"), r.get("rep"), r.get("step")) == (quant, rep, step)]
    return hits[-1] if hits else None


def do_step(quant, rep, step, prompt, parent_svg):
    b = base(quant, rep, step)
    snap = gpu_snapshot()
    try:
        g = generate(prompt)
    except Exception as e:
        record({"quant": quant, "rep": rep, "step": step, "error": repr(e)[:300],
                "gpu": snap, "ts": time.time()})
        return
    rec = {"quant": quant, "rep": rep, "step": step, "finish": g["finish"],
           "tokens": g["tokens"], "prompt_tokens": g["prompt_tokens"],
           "reasoning_chars": g["reasoning_chars"], "elapsed_s": g["elapsed_s"],
           "gpu": snap, "ts": time.time(), "has_svg": g["svg"] is not None}
    Path(b + ".content.txt").write_text(g["content"])
    if g["svg"]:
        Path(b + ".svg").write_text(g["svg"])
        pr = probe(b + ".svg", b + ".png")
        Path(b + ".grid.txt").write_text(pr.get("grid") or "")
        n = pr.get("notes") or {}
        rec.update(score=pr.get("score"), max=pr.get("max"), checks=pr.get("checks"),
                   n_components=n.get("n_components"),
                   largest_frac=n.get("largest_component_frac"),
                   identical_to_parent=(parent_svg is not None
                                        and g["svg"].strip() == parent_svg.strip()))
    else:
        rec.update(score=0, max=None, checks=None)
    record(rec)


def needs_goal3(quant, rep):
    r = last(quant, rep, "goal2")
    return bool(r and r.get("max") and r.get("score") is not None and r["score"] < r["max"])


def needs_work(quant, rep):
    done = {(r.get("quant"), r.get("rep"), r.get("step")) for r in records()}
    for s in ("p1", "intent2", "goal2"):
        if (quant, rep, s) not in done:
            return True
    return needs_goal3(quant, rep) and (quant, rep, "goal3") not in done


def run_rep(quant, rep):
    done = lambda s: last(quant, rep, s) is not None
    if not done("p1"):
        do_step(quant, rep, "p1", TASK, None)
    p1, g1 = load(quant, rep, "p1", ".svg"), load(quant, rep, "p1", ".grid.txt")
    if not p1 or g1 is None:
        return
    for fr in ("intent", "goal"):
        if not done(f"{fr}2"):
            do_step(quant, rep, f"{fr}2", scaffold(p1, g1, fr), p1)
    if needs_goal3(quant, rep) and not done("goal3"):
        g2, gg = load(quant, rep, "goal2", ".svg"), load(quant, rep, "goal2", ".grid.txt")
        if g2 and gg is not None:
            do_step(quant, rep, "goal3", scaffold(g2, gg, "goal"), g2)


def dry_run():
    src = ROOT / "data/receipts/svgbench-run/pass1.svg"
    png = "/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/dry.png"
    grid = probe(src, png)["grid"]
    a, b = scaffold(src.read_text(), grid, "intent"), scaffold(src.read_text(), grid, "goal")
    # Rigorous one-variable check. A character diff fragments a single sentence swap into many
    # spans, so "all spans look like they are inside the clause" is an eyeball judgement.
    # Substituting each clause with the same placeholder and demanding byte-identical remainders
    # is not: if anything else differs, this fails.
    once = a.count(CLAUSE["intent"]) == 1 and b.count(CLAUSE["goal"]) == 1
    same = a.replace(CLAUSE["intent"], "<CLAUSE>") == b.replace(CLAUSE["goal"], "<CLAUSE>")
    print(f"  intent scaffold {len(a)} chars, goal scaffold {len(b)} chars")
    print(f"  each clause appears exactly once:          {once}")
    print(f"  byte-identical outside the review clause:  {same}")
    if not (once and same):
        raise SystemExit("  *** arms differ in more than the review clause -- do not launch ***")
    print("\n  --- tail of goal scaffold as the model will see it ---")
    print("  " + b[-300:].replace("\n", "\n  "))
    print("\n  plan (rep-major interleave):")
    for rep in range(1, REPS + 1):
        print("   ", " -> ".join(f"{q}/r{rep}" for q, _ in QUANTS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.dry_run:
        dry_run()
        return
    for rep in range(1, REPS + 1):
        for quant, model in QUANTS:
            if not needs_work(quant, rep):
                continue
            print(f"{time.strftime('%H:%M:%S')} === {quant} rep {rep} ===", flush=True)
            p, ok = start_server(model, OUT / f"server_{quant}_r{rep}.log")
            if not ok:
                record({"quant": quant, "rep": rep, "step": "server", "error": "server never ready",
                        "ts": time.time()})
                stop_server(p)
                continue
            try:
                run_rep(quant, rep)
            finally:
                stop_server(p)
    print(f"{time.strftime('%H:%M:%S')} === LADDER COMPLETE ===", flush=True)


if __name__ == "__main__":
    main()
