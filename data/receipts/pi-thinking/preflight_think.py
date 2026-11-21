#!/usr/bin/env python3
"""PLAN_SIZING.md preflight, per server: with the xhigh kwargs, (1) all three outcome descriptions render, (2) the xhigh
instruction is present, (3) an earlier assistant turn's reasoning_content appears in the rendered prompt, (4) the
generation prompt opens a think block. Exit 0 only if all four hold. Usage: preflight_think.py ARM URL OUT_JSON"""
import json, sys, tempfile
from pathlib import Path
import httpx
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "argus" / "gaming")); sys.path.insert(0, str(ROOT / "argus" / "gaming" / "families"))
import k3_data, texts_v1 as T  # noqa: E402
from preflight_v1 import OUTCOME_PHRASES  # noqa: E402

import os
EFFORT = os.environ.get("THINK_EFFORT", "xhigh")      # xhigh: the sentence must be injected; medium: nothing may be
KW = {"enable_thinking": True, "reasoning_effort": EFFORT}
SENTINEL = "SENTINEL_REASONING_4471"


def render(url, messages):
    body = {"messages": messages, "tools": T.TOOLS, "chat_template_kwargs": KW}
    return httpx.post(f"{url}/apply-template", json=body, timeout=120).json().get("prompt", "")


def main(arm, url, out):
    task = k3_data.build(Path(tempfile.mkdtemp()) / "t", "K3", "shallow", 2)
    first = [{"role": "system", "content": T.SYSTEM}, {"role": "user", "content": task["instruction"]}]
    p1 = render(url, first)
    call = {"id": "c1", "type": "function", "function": {"name": "list_dir", "arguments": json.dumps({"path": "."})}}
    hist = first + [{"role": "assistant", "content": "", "reasoning_content": SENTINEL, "tool_calls": [call]},
                    {"role": "tool", "tool_call_id": "c1", "content": "exit code 0\nSPEC.md"}]
    p2 = render(url, hist)
    off = httpx.post(f"{url}/apply-template", timeout=120, json={"messages": first, "tools": T.TOOLS,
                     "chat_template_kwargs": {"enable_thinking": False}}).json().get("prompt", "")
    n = lambda s: len(httpx.post(f"{url}/tokenize", json={"content": s}, timeout=120).json().get("tokens", []))
    checks = {"outcomes_rendered": all(p in p1 for p in OUTCOME_PHRASES),
              "effort_text_as_expected": bool(p1) and (("Reasoning effort is set to xhigh" in p1) if EFFORT == "xhigh" else ("Reasoning effort is set" not in p1)),
              "reasoning_replayed": SENTINEL in p2,
              "think_opened": p1.rstrip().endswith("<think>")}
    rec = {"arm": arm, "checks": checks, "ok": all(checks.values()), "tokens_xhigh": n(p1), "tokens_off": n(off),
           "added_by_xhigh": [ln for ln in p1.splitlines() if ln not in off.splitlines()][:12],
           "prompt_xhigh_head": p1[:1200], "prompt_xhigh_tail": p1[-300:], "history_tail": p2[-700:]}
    rows = json.loads(Path(out).read_text()) if Path(out).exists() else {}
    rows[arm] = rec
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(rows, indent=1))
    print(f"preflight {arm}: {checks} | first request {rec['tokens_xhigh']} tokens (thinking off {rec['tokens_off']})")
    return rec["ok"]


if __name__ == "__main__":
    sys.exit(0 if main(*sys.argv[1:4]) else 1)
