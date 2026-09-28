#!/usr/bin/env python3
"""PREREG_LFM25_MODES.md driver: DavidAU's LFM2.5-2.6B Turbo-Brilliance modes on the 16 CAL items, two templates.

One server per template, the same GGUF:
  ORIG  the template embedded in the GGUF                  modes off low high ultra einstein spoon omni
  TRIM  the same template with two comment tags left-trimmed modes off high omni
        (make_trimmed_template.py: removes the stray "\\n\\n" token after BOS and nothing else, 58/58 renders checked)

Each request: the CAL tier prompt (fixture_v0_beta.json) with "{REASON:<mode>} " prepended to the user message,
DavidAU's tester sampling (temp 1.0, top_k 64, min_p 0.05, top_p 0.95, repeat penalty off), max_tokens 16000,
cache_prompt false, a per-request seed. Graded with the fixture's own pick_answer() and classify().

Gate G1 runs before any row and aborts the run on failure:
- every mode's tag is stripped from the render;
- the injected prompt has the registered token count (TRIM = ORIG - 1);
- the TRIM server's template carries the two edits;
- both servers serve the same file.

Rows: one per (template, mode, seed, item), flush + fsync, resumable. Order interleaves modes inside each (seed,
item) so any drift over the run hits every mode alike.
Usage: lfm25_modes.py [--orig http://127.0.0.1:8095] [--trim http://127.0.0.1:8096] [--out lfm25_modes/rows.jsonl]
"""
import argparse, json, os, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "viability"))
from run_fixture_structfix import classify, pick_answer  # noqa: E402  (the CAL grader, unchanged)

FIX = json.load(open(HERE.parent / "viability" / "fixture_v0_beta.json"))["tier_cal"]
ARMS = {"ORIG": ["off", "low", "high", "ultra", "einstein", "spoon", "omni"], "TRIM": ["off", "high", "omni"]}
SEEDS = [1001, 1002, 1003]
SAMPLING = {"temperature": 1.0, "top_k": 64, "min_p": 0.05, "top_p": 0.95, "repeat_penalty": 1.0}
MAX_TOKENS = 16000
# registered injected-prompt sizes (tokens in the rendered prompt for "{REASON:<mode>} What is 17*19?", ORIG)
REG_TOKENS = {"off": 18, "low": 76, "high": 170, "ultra": 345, "einstein": 320, "spoon": 822, "omni": 995}


def post(url, path, body, timeout=1800):
    req = urllib.request.Request(url + path, json.dumps(body).encode(), {"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def get(url, path):
    return json.load(urllib.request.urlopen(url + path, timeout=30))


def gate(urls):
    """G1: abort unless the tag handling, token counts, template edit and model identity hold."""
    props = {k: get(u, "/props") for k, u in urls.items()}
    paths = {k: p["model_path"] for k, p in props.items()}
    assert len(set(paths.values())) == 1, f"G1: servers serve different files: {paths}"
    assert "{#- --- REASONING TAG DETECTION START" in props["TRIM"]["chat_template"], "G1: TRIM template lacks the edit"
    assert "{#- --- REASONING TAG DETECTION START" not in props["ORIG"]["chat_template"], "G1: ORIG template is edited"
    for m, want in REG_TOKENS.items():
        for k, u in urls.items():
            msg = [{"role": "user", "content": "{REASON:%s} What is 17*19?" % m}]
            prompt = post(u, "/apply-template", {"messages": msg, "chat_template_kwargs": {"enable_thinking": True}})["prompt"]
            assert "{REASON:" not in prompt, f"G1: {k}/{m} tag not stripped"
            n = len(post(u, "/tokenize", {"content": prompt})["tokens"])
            exp = want if k == "ORIG" else want - 1
            assert n == exp, f"G1: {k}/{m} renders {n} tokens, registered {exp}"
    return paths["ORIG"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig", default="http://127.0.0.1:8095")
    ap.add_argument("--trim", default="http://127.0.0.1:8096")
    ap.add_argument("--out", default=str(HERE / "lfm25_modes" / "rows.jsonl"))
    a = ap.parse_args()
    urls = {"ORIG": a.orig, "TRIM": a.trim}
    model = gate(urls)
    print("G1 passed; serving", model, flush=True)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for l in open(out):
            try:
                r = json.loads(l); done.add((r["template"], r["mode"], r["seed"], r["id"]))
            except (json.JSONDecodeError, KeyError):
                pass
    with open(out, "a") as f:
        for seed in SEEDS:
            for it in FIX["items"]:
                for tpl, modes in ARMS.items():
                    for mode in modes:
                        key = (tpl, mode, seed, it["id"])
                        if key in done:
                            continue
                        user = "{REASON:%s} " % mode + FIX["prompt"].format(q=it["q"])
                        body = {"messages": [{"role": "user", "content": user}], "max_tokens": MAX_TOKENS,
                                "cache_prompt": False, "seed": seed, **SAMPLING}
                        t0 = time.time()
                        try:
                            r = post(urls[tpl], "/v1/chat/completions", body)
                            ch = r["choices"][0]; msg = ch["message"]
                            content, reasoning = msg.get("content") or "", msg.get("reasoning_content") or ""
                            fin = ch.get("finish_reason")
                            got, nm = pick_answer(content, reasoning, fin)
                            row = {"template": tpl, "mode": mode, "seed": seed, "id": it["id"], "arm": it["arm"],
                                   "gold": it["gold"], "finish": fin, "got": got, "n_matches": nm,
                                   "grade": classify(got, it["gold"]) if fin != "length" else "NO-STOP",
                                   "completion_tokens": r["usage"]["completion_tokens"],
                                   "prompt_tokens": r["usage"]["prompt_tokens"], "reasoning_chars": len(reasoning),
                                   "content": content[-2000:], "secs": round(time.time() - t0, 1),
                                   "tps": (r.get("timings") or {}).get("predicted_per_second")}
                        except Exception as e:                       # noqa: BLE001  (recorded, never skipped)
                            row = {"template": tpl, "mode": mode, "seed": seed, "id": it["id"], "arm": it["arm"],
                                   "gold": it["gold"], "grade": "ERROR", "error": f"{type(e).__name__}: {e}"[:300]}
                        f.write(json.dumps(row, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
                        print(f"{tpl} {mode:9s} s{seed} {it['id']:7s} {row['grade']:16s} {row.get('completion_tokens', '-'):>6} tok",
                              flush=True)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
