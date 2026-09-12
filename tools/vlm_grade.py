#!/usr/bin/env python3
"""A controlled local vision grader: score images against a written rubric, reproducibly.

Built 2026-09-11 after a vendor web chat proved unusable as an instrument — the served model,
system prompt and personalisation were all unknowable, and our own captioned contact sheet leaked
the answer key to it (`data/receipts/svgbench-pelican3/RESULT_VLM_LABEL_LEAK.md`).

What this pins, so a receipt can state it:
  - model + mmproj file paths, sizes and sha256
  - the llama-server binary, its commit, and every flag
  - the rubric prompt and its sha256
  - sampling (temperature 0 by default) and the number of repeats

Three properties matter more than convenience:

**Blind by construction.** The model is never sent a filename, a label, a score or an arm name.
Images are keyed by an opaque code; the code->file mapping is written to a separate file that the
prompt never touches.

**Positive controls gate the run.** Synthetic images with known content are graded first, and the
run ABORTS if the model cannot describe them. A loaded server that answers is not evidence that it
can see — `readiness-probes-lie`, and a vision model that silently ignores the image would produce
plausible scores from the prompt alone.

**Repeats are mandatory.** One pass is an existence proof, not a rate. Every image is graded --reps
times and the spread is reported, which is the machine equivalent of the repeated-pair check used on
human raters.

Usage:
  vlm_grade.py --images DIR --rubric tools/vlm_rubrics/pelican_capability.txt --out OUTDIR [--reps 3]
  vlm_grade.py --images a.png b.png --rubric R.txt --out OUTDIR --base-url http://127.0.0.1:8092
"""
import argparse, base64, hashlib, io, json, os, random, re, signal, subprocess, sys, time
from pathlib import Path
from urllib import request as urlreq

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "/mnt/TG_2TB/AI/Models/Qwen 3.8/27B/Qwen3.8-27B-UD-IQ3_XXS.gguf"
DEFAULT_MMPROJ = "/mnt/TG_2TB/AI/Models/qwen38-mmproj/mmproj-F16.gguf"
DEFAULT_SERVER = "/mnt/TG_2TB/Projects/buun-aad85/build_rocm/bin/llama-server"
MEM_FLOOR_GB = 2.5          # the desktop outranks the benchmark
MEM_START_GB = 6.0


def sha256(path, cap=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
            if cap and f.tell() > cap:
                break
    return h.hexdigest()


def mem_available_gb():
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1048576
    return None


def vram_used_mib():
    for c in Path("/sys/class/drm").glob("card*/device/mem_info_vram_used"):
        try:
            return int(c.read_text()) // 1048576
        except OSError:
            pass
    return None


def square_white(path):
    """Pad to a square on white.

    The preprocessor letterboxes non-square images, and on 2026-09-11 the model described the
    padding ('framed by black bars') as if it were content. White padding matches these drawings'
    own backdrop and keeps the artefact out of the judgement.
    """
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    flat = Image.new("RGB", im.size, "white")
    flat.paste(im, mask=im.split()[3])
    s = max(flat.size)
    sq = Image.new("RGB", (s, s), "white")
    sq.paste(flat, ((s - flat.width) // 2, (s - flat.height) // 2))
    buf = io.BytesIO()
    sq.save(buf, format="PNG")
    return buf.getvalue()


def post(base_url, body, timeout=300):
    req = urlreq.Request(base_url + "/v1/chat/completions",
                         data=json.dumps(body).encode(),
                         headers={"Content-Type": "application/json"})
    with urlreq.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def ask_image(base_url, png_bytes, prompt, max_tokens, temperature, timeout=300):
    b64 = base64.b64encode(png_bytes).decode()
    body = {"messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}]}],
            "max_tokens": max_tokens, "temperature": temperature}
    o = post(base_url, body, timeout)
    m = o["choices"][0]["message"]
    return ((m.get("content") or "").strip(),
            (m.get("reasoning_content") or "").strip(),
            (o.get("usage") or {}).get("completion_tokens"))


def parse_score(text):
    """Pull {"score": int, "reason": str} out of a reply, tolerating code fences and prose."""
    if not text:
        return None, None
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            j = json.loads(m.group(0))
            s = j.get("score")
            if isinstance(s, (int, float)):
                return int(round(s)), str(j.get("reason", ""))[:200]
        except Exception:
            pass
    m = re.search(r"\b([1-9]|10)\s*(?:/\s*10)?\b", t)          # bare number fallback
    return (int(m.group(1)), t[:200]) if m else (None, t[:200])


CONTROLS = [
    ("red circle", lambda d, s: d.ellipse([s*0.28, s*0.28, s*0.72, s*0.72], fill=(220, 30, 30)),
     lambda a: "red" in a.lower() and ("circle" in a.lower() or "dot" in a.lower())),
    ("blue square", lambda d, s: d.rectangle([s*0.3, s*0.3, s*0.7, s*0.7], fill=(30, 60, 210)),
     lambda a: "blue" in a.lower() and ("square" in a.lower() or "rectangle" in a.lower())),
    ("blank", lambda d, s: None, lambda a: "blank" in a.lower()),
]


def run_controls(base_url, temperature, log):
    """Grade synthetic images with known content. Returns True only if every control passes."""
    from PIL import Image, ImageDraw
    ok = True
    for name, draw, check in CONTROLS:
        im = Image.new("RGB", (320, 320), "white")
        draw(ImageDraw.Draw(im), 320)
        buf = io.BytesIO(); im.save(buf, format="PNG")
        ans, _, _ = ask_image(base_url, buf.getvalue(),
                              "Describe exactly what you see in one short sentence. "
                              "If the image is blank, reply with the single word BLANK.",
                              50, temperature)
        good = check(ans)
        ok &= good
        log(f"  control {name:12s} {'PASS' if good else 'FAIL'}  -> {ans[:90]!r}")
    return ok


def start_server(args, log):
    cmd = [args.server, "-m", args.model, "--mmproj", args.mmproj,
           "-ngl", "99", "-c", str(args.ctx), "-np", "1", "-fa", "on", "--kv-unified",
           "-ctk", "q8_0", "-ctv", "q8_0", "--chat-template-kwargs",
           json.dumps({"enable_thinking": False}), "--temp", str(args.temperature),
           "--jinja", "--host", "127.0.0.1", "--port", str(args.port)]
    log("  " + " ".join(repr(c) if " " in c else c for c in cmd))
    logf = open(Path(args.out) / "server.log", "w")
    p = subprocess.Popen(cmd, stdout=logf, stderr=logf, start_new_session=True)
    base = f"http://127.0.0.1:{args.port}"
    for _ in range(140):
        if p.poll() is not None:
            log("  server exited during load; see server.log")
            return p, None
        try:                                    # a real completion, not /health: a 200 is not proof
            post(base, {"messages": [{"role": "user", "content": "Say READY"}], "max_tokens": 4}, 6)
            return p, base
        except Exception:
            time.sleep(3)
    return p, None


def stop_server(p):
    if p is None:
        return
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        p.wait(40)
    except Exception:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", nargs="+", required=True, help="image files, or a directory of .png")
    ap.add_argument("--rubric", required=True, help="file holding the grading prompt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--mmproj", default=DEFAULT_MMPROJ)
    ap.add_argument("--server", default=DEFAULT_SERVER)
    ap.add_argument("--base-url", default=None, help="use an already-running server instead of starting one")
    ap.add_argument("--port", type=int, default=8092)
    ap.add_argument("--ctx", type=int, default=8192)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=120)
    ap.add_argument("--seed", type=int, default=20260911, help="seeds the code labels and image order")
    ap.add_argument("--skip-controls", action="store_true", help="NOT recommended; recorded in the manifest")
    a = ap.parse_args()

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    logfh = open(out / "run.log", "a")
    def log(m):
        print(m, flush=True)
        logfh.write(m + "\n"); logfh.flush(); os.fsync(logfh.fileno())

    files = []
    for x in a.images:
        p = Path(x)
        files.extend(sorted(p.glob("*.png")) if p.is_dir() else [p])
    files = [f for f in files if f.is_file()]
    if not files:
        sys.exit("no images found")

    rubric = Path(a.rubric).read_text().strip()
    rnd = random.Random(a.seed)
    codes = {}
    for f in files:                              # opaque labels; the model never sees a filename
        while True:
            c = "".join(rnd.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
            if c not in codes.values():
                codes[str(f)] = c
                break

    mem = mem_available_gb()
    if mem is not None and mem < MEM_START_GB:
        sys.exit(f"only {mem:.1f} GB MemAvailable; refusing to start (need {MEM_START_GB})")

    manifest = {
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": {"path": a.model, "bytes": os.path.getsize(a.model), "sha256": sha256(a.model)},
        "mmproj": {"path": a.mmproj, "bytes": os.path.getsize(a.mmproj), "sha256": sha256(a.mmproj)},
        "server_binary": a.server,
        "server_commit": subprocess.run(["git", "-C", str(Path(a.server).parents[2]), "rev-parse", "--short", "HEAD"],
                                        capture_output=True, text=True).stdout.strip() or None,
        "rubric_sha256": hashlib.sha256(rubric.encode()).hexdigest(),
        "rubric": rubric,
        "reps": a.reps, "temperature": a.temperature, "ctx": a.ctx,
        "max_tokens": a.max_tokens, "seed": a.seed,
        "enable_thinking": False,
        "controls_skipped": bool(a.skip_controls),
        "n_images": len(files),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (out / "mapping.json").write_text(json.dumps({v: k for k, v in codes.items()}, indent=1))
    log(f"{len(files)} images x {a.reps} reps | model sha {manifest['model']['sha256'][:12]} | "
        f"rubric sha {manifest['rubric_sha256'][:12]}")

    proc = None
    base = a.base_url
    try:
        if base is None:
            log("starting server:")
            proc, base = start_server(a, log)
            if base is None:
                sys.exit("server never produced a completion")
        log(f"server ready at {base} | VRAM {vram_used_mib()} MiB")

        if not a.skip_controls:
            log("positive controls (the run aborts if the model cannot see):")
            if not run_controls(base, a.temperature, log):
                sys.exit("POSITIVE CONTROL FAILED — not grading; the model is not reading the image")
        else:
            log("WARNING: positive controls skipped by request")

        done = set()
        res_path = out / "results.jsonl"
        if res_path.exists():                    # resumable
            for line in open(res_path):
                try:
                    r = json.loads(line)
                    done.add((r["code"], r["rep"]))
                except Exception:
                    pass
        order = [(f, rep) for rep in range(1, a.reps + 1) for f in files]
        rnd.shuffle(order)                       # decorrelate order from identity
        with open(res_path, "a") as fh:
            for f, rep in order:
                code = codes[str(f)]
                if (code, rep) in done:
                    continue
                m = mem_available_gb()
                if m is not None and m < MEM_FLOOR_GB:
                    log(f"ABORT: MemAvailable {m:.1f} GB < {MEM_FLOOR_GB}")
                    break
                t0 = time.time()
                try:
                    content, reasoning, tok = ask_image(base, square_white(f), rubric,
                                                        a.max_tokens, a.temperature)
                    score, reason = parse_score(content)
                    rec = dict(code=code, rep=rep, score=score, reason=reason, raw=content[:400],
                               reasoning_chars=len(reasoning), tokens=tok,
                               elapsed_s=round(time.time() - t0, 1), ts=time.time())
                except Exception as e:
                    rec = dict(code=code, rep=rep, score=None, error=repr(e)[:200], ts=time.time())
                fh.write(json.dumps(rec) + "\n"); fh.flush(); os.fsync(fh.fileno())
                log(f"  {code} rep{rep}: score {rec.get('score')}  {str(rec.get('reason'))[:60]}")
    finally:
        stop_server(proc)

    rows = [json.loads(l) for l in open(out / "results.jsonl") if l.strip()]
    per = {}
    for r in rows:
        if r.get("score") is not None:
            per.setdefault(r["code"], []).append(r["score"])
    log("\n=== per image (code -> scores across reps) ===")
    inv = {v: k for k, v in codes.items()}
    for code, ss in sorted(per.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
        spread = max(ss) - min(ss) if len(ss) > 1 else 0
        log(f"  {code}  {sorted(ss, reverse=True)}  mean {sum(ss)/len(ss):.2f}  spread {spread}  "
            f"{Path(inv[code]).name}")
    if per:
        spreads = [max(s) - min(s) for s in per.values() if len(s) > 1]
        if spreads:
            log(f"\nself-consistency: mean spread across reps {sum(spreads)/len(spreads):.2f}, "
                f"max {max(spreads)}  ({sum(1 for s in spreads if s == 0)}/{len(spreads)} identical)")
    log(f"\nwrote {out/'results.jsonl'}, manifest.json, mapping.json")


if __name__ == "__main__":
    main()
