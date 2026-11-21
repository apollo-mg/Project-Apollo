#!/usr/bin/env python3
"""Preserved-reasoning replay probe (Mark's question 11-19; BACKLOG row; PREREG_SEED2.md). For every impossible-item
episode recorded with thinking on and its exact history (`messages`), the deciding steps are (a) the reply that called
finish (the last one), and (b) the first reply after the reminder, when that is a different reply. Each is re-asked
twice with the episode's settings (xhigh, greedy, 16k, prompt cache off, the v1 tools):
  KEPT     = the recorded history up to that reply, unchanged -- it should reproduce the recorded reply (the control);
  STRIPPED = the same history with every earlier reply's reasoning_content removed, nothing else changed.
The next action of each (tool name, plus the outcome for finish) is recorded, one line per probe, flushed and fsynced.
Usage: probe_preserve.py URL RAW_DIR OUT_JSONL"""
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "argus" / "gaming")); sys.path.insert(0, str(ROOT / "argus" / "gaming" / "families"))
import run_v1, texts_v1 as T  # noqa: E402


def action(msg):
    calls = (msg or {}).get("tool_calls") or []
    if not calls:
        return "no_tool_call"
    f = calls[0]["function"]
    if f["name"] != "finish":
        return f["name"]
    try:
        a = f.get("arguments") or "{}"
        a = json.loads(a) if isinstance(a, str) else a
        return f"finish:{a.get('outcome')}"
    except (ValueError, TypeError, AttributeError):
        return "finish:?"


def deciding(msgs):
    """[(kind, index of the assistant reply)] for the last finish and the first reply after the reminder."""
    asst = [i for i, m in enumerate(msgs) if m.get("role") == "assistant"]
    out = []
    fin = [i for i in asst if action(msgs[i]).startswith("finish")]
    rem = next((i for i, m in enumerate(msgs) if m.get("role") == "tool" and T.REMINDER in (m.get("content") or "")), None)
    after = next((i for i in asst if rem is not None and i > rem), None)
    if after is not None:
        out.append(("after_reminder", after))
    if fin and fin[-1] != after:
        out.append(("finish", fin[-1]))
    return out


def strip(prefix):
    return [{k: v for k, v in m.items() if k != "reasoning_content"} for m in prefix]


def main(url, raw, out):
    chats = {}
    done = set()
    if Path(out).exists():
        done = {(r["item"], r["kind"]) for r in map(json.loads, open(out))}
    for f in sorted(Path(raw).glob("*.json")):
        if f.name.endswith(".partial.json"):
            continue
        rec = json.load(open(f))
        if rec.get("rung") != "impossible" or "messages" not in rec:
            continue
        msgs = rec["messages"]
        effort = rec.get("think") or "xhigh"                     # the episode's own effort (xhigh or medium)
        chat = chats.setdefault(effort, run_v1.chat_fn(url, 16384, 3600, effort))
        for kind, d in deciding(msgs):
            if (rec["item"], kind) in done:
                continue
            prefix = msgs[:d]
            n_strip = sum(len(m.get("reasoning_content") or "") for m in prefix)
            row = {"arm": rec["arm"], "item": rec["item"], "kind": kind, "index": d, "row": rec["row"], "think": effort,
                   "reasoning_chars_stripped": n_strip, "recorded": action(msgs[d])}
            if n_strip == 0:
                row["skipped"] = "no earlier reasoning to strip"
            else:
                for name, hist in (("kept", prefix), ("stripped", strip(prefix))):
                    try:
                        m = chat(hist, T.V1["tools"])
                        row[name] = action(m)
                        row[name + "_usage"] = m.get("_usage")
                        row[name + "_reasoning"] = m.get("reasoning_content") or ""
                        row[name + "_content"] = m.get("content") or ""
                    except Exception as e:                       # recorded, not retried: the probe is one request each
                        row[name] = f"error: {type(e).__name__}: {str(e)[:200]}"
                row["kept_reproduces"] = row.get("kept") == row["recorded"]
                row["stripped_differs"] = row.get("stripped") != row.get("kept")
            with open(out, "a") as fh:
                fh.write(json.dumps(row) + "\n"); fh.flush(); os.fsync(fh.fileno())
            print(f"probe {row['arm']} {row['item']} {kind}: recorded {row['recorded']} | kept {row.get('kept')} | "
                  f"stripped {row.get('stripped')} | {n_strip} chars stripped", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:4])
