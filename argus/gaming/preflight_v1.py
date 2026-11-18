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


def _strip_ids(m):
    """llama-server gives every tool call a random id; the chat template never renders it (checked: no 'id' in the
    template), so the model cannot see it. Everything else in the message is compared."""
    m = dict(m)
    if m.get("tool_calls"):
        m["tool_calls"] = [{k: v for k, v in c.items() if k != "id"} for c in m["tool_calls"]]
    return json.dumps(m, sort_keys=True)


def leak(a, b):
    A, B = json.load(open(a)), json.load(open(b))
    ta, tb = [_strip_ids(m) for m in A["transcript"]], [_strip_ids(m) for m in B["transcript"]]
    la = [(e["tool"], json.dumps(e.get("args", {}), sort_keys=True), e.get("out")) for e in A["log"]]
    lb = [(e["tool"], json.dumps(e.get("args", {}), sort_keys=True), e.get("out")) for e in B["log"]]
    same = ta == tb and la == lb
    first = next((i for i, (x, y) in enumerate(zip(ta, tb)) if x != y), None if len(ta) == len(tb) else min(len(ta), len(tb)))
    print(f"leak check: {len(ta)} vs {len(tb)} model messages, {len(la)} vs {len(lb)} tool steps; identical apart from "
          f"server tool-call ids: {same}; first difference at {first}")
    return same


if __name__ == "__main__":
    ok = template(*sys.argv[2:5]) if sys.argv[1] == "template" else leak(*sys.argv[2:4])
    sys.exit(0 if ok else 1)
