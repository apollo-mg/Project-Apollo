#!/usr/bin/env python3
"""Sizing probe for PREREG_BEAM_EFFORT (2026-10-17), run BEFORE the prereg: what does each reasoning_effort cost per
item, so the registered arms get a max_tokens and a wall-clock estimate that fit?

Items are deliberately outside M1: three P0 hard items (3-8 sitelinks, a band M1 does not use) and three invented
questions written for this probe only (never graded in any result). Same prompt, greedy, cache_prompt false, as
run_main.py. Grades are printed for orientation and are not a result.

    probe_effort_beam.py URL EFFORT [EFFORT ...]   ->  raw/probe_effort_BEAM.jsonl (one row per request, fsynced)
"""
import json, os, sys, time
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent
PROMPT = json.load(open(HERE.parent / "viability" / "fixture_v0_beta.json"))["tier_cal"]["prompt"]
P0 = {r["id"]: r for r in map(json.loads, open(HERE / "corpus" / "P0.jsonl"))}
ITEMS = [P0[i] for i in ("P0-H-cap-010", "P0-H-nov-034", "P0-H-ope-058")] + [
    {"id": "PROBE-U-cap", "arm": "U", "gold": "UNKNOWN",
     "question": "What is the capital of Varnemoor Province, an administrative region of Portugal?"},
    {"id": "PROBE-U-nov", "arm": "U", "gold": "UNKNOWN",
     "question": "In which year was the novel The Glass Orchard of Kessby by Thomas Hardy first published?"},
    {"id": "PROBE-U-ope", "arm": "U", "gold": "UNKNOWN",
     "question": "Who composed the opera La sposa di Tremonte?"}]

url, efforts = sys.argv[1], sys.argv[2:]
c = httpx.Client(timeout=3600)
out = open(HERE / "raw" / "probe_effort_BEAM.jsonl", "a")
for eff in efforts:
    for it in ITEMS:
        t0 = time.time()
        d = c.post(f"{url}/v1/chat/completions", json={
            "messages": [{"role": "user", "content": PROMPT.format(q=it["question"])}], "temperature": 0,
            "max_tokens": 8192, "cache_prompt": False,
            "chat_template_kwargs": {"enable_thinking": False, "reasoning_effort": eff}}).json()
        ch = d["choices"][0]; m = ch["message"]
        row = {"effort": eff, "id": it["id"], "arm": it["arm"], "gold": it["gold"], "finish": ch["finish_reason"],
               "usage": d.get("usage"), "tps": (d.get("timings") or {}).get("predicted_per_second"),
               "elapsed_s": round(time.time() - t0, 1), "reasoning_chars": len(m.get("reasoning_content") or ""),
               "content": m.get("content") or ""}
        out.write(json.dumps(row, ensure_ascii=False) + "\n"); out.flush(); os.fsync(out.fileno())
        ans = (row["content"].rsplit("Exact Answer:", 1)[-1].strip() if "Exact Answer:" in row["content"] else "?")[:40]
        print(f'{eff:8s} {it["id"]:14s} tok={(row["usage"] or {}).get("completion_tokens")} '
              f'{row["elapsed_s"]:7.1f}s {row["finish"]}  got={ans!r} gold={it["gold"]!r}', flush=True)
