#!/usr/bin/env python3
"""CALIBRATION_v1.md preflight helpers.
  template ARM URL OUT_JSON   the v1 first request through the served template: all three outcomes must appear
  leak A.json B.json          two runs of one item at different contexts: every model message must be identical
Exit status 1 on a failed check."""
import json, sys
from pathlib import Path
import httpx
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "families"))
import texts_v1 as T, f2v1  # noqa: E402

OUTCOME_PHRASES = ("completed: the task is done", "impossible: the task cannot", "not_completed: you are stopping")


def template(arm, url, out):
    import tempfile
    task = f2v1.build(Path(tempfile.mkdtemp()) / "t", "ranges", "K1", "deep", 1)
    body = {"messages": [{"role": "system", "content": T.SYSTEM}, {"role": "user", "content": task["instruction"]}],
            "tools": T.TOOLS, "chat_template_kwargs": {"enable_thinking": False}}
    prompt = httpx.post(f"{url}/apply-template", json=body, timeout=120).json().get("prompt", "")
    n = len(httpx.post(f"{url}/tokenize", json={"content": prompt}, timeout=120).json().get("tokens", []))
    found = {p: p in prompt for p in OUTCOME_PHRASES}
    rec = {"arm": arm, "prompt_tokens": n, "outcomes_rendered": found, "ok": all(found.values()), "prompt_tail": prompt[-400:]}
    rows = json.loads(Path(out).read_text()) if Path(out).exists() else {}
    rows.setdefault("template", {})[arm] = rec
    Path(out).write_text(json.dumps(rows, indent=1))
    print(f"template {arm}: {n} tokens, outcomes rendered {found}")
    return rec["ok"]


def leak(a, b):
    ta = [json.dumps(m, sort_keys=True) for m in json.load(open(a))["transcript"]]
    tb = [json.dumps(m, sort_keys=True) for m in json.load(open(b))["transcript"]]
    same = ta == tb
    first = next((i for i, (x, y) in enumerate(zip(ta, tb)) if x != y), None if len(ta) == len(tb) else min(len(ta), len(tb)))
    print(f"leak check: {len(ta)} vs {len(tb)} model messages; identical={same}; first difference at {first}")
    return same


if __name__ == "__main__":
    ok = template(*sys.argv[2:5]) if sys.argv[1] == "template" else leak(*sys.argv[2:4])
    sys.exit(0 if ok else 1)
