#!/usr/bin/env python3
"""Nightly content digest: merge the last 7 days of hourly captures (tools/content_capture.py) into topics, let a later
capture update an earlier topic's hook (an outcome, a correction), rank them, and render
data/dev_diaries/content/this_week.md, the talk sheet for the weekly video. On Saturdays the sheet is also kept as
week_<date>.md. Private and gitignored, like the captures it quotes.

One model call over the whole window, not embeddings and thresholds (2026-10-17: the call returns only titles, hooks,
ids and a status; per-topic talking points made 50 captures overrun a 4,000-token budget, and the captured timeline
already carries the facts): a week of captures is a few thousand tokens, and
"is this the same story, and did it get an ending?" is a judgement, not a similarity score. Facts on the sheet (dates,
numbers, quotes, evidence) come from the captures, which were grounded against the session text; the model's hooks are labelled
as model text. If the model fails, the sheet is still written, ungrouped, and the
heartbeat says degraded.

Prints one JSON summary line (status, topics, captures, path) for daydream_nightly.sh.
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime, timedelta

ROOT = "/mnt/TG_2TB/Projects/Apollo"
CDIR = f"{ROOT}/data/dev_diaries/content"
GH = "https://github.com/apollo-mg/Project-Apollo/blob/main/"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from content_capture import load_deny, denied  # noqa: E402

SCHEMA = {"type": "object", "required": ["topics"], "properties": {"topics": {"type": "array", "items": {
    "type": "object", "required": ["title", "hook", "ids", "status"],
    "properties": {"title": {"type": "string"}, "hook": {"type": "string"},
                   "ids": {"type": "array", "items": {"type": "string"}},
                   "status": {"type": "string", "enum": ["ready", "developing", "weak"]}}}}}}

PROMPT = """Below are items captured during the past week of a hobbyist's local-LLM lab work, each with an id and a
date. They are raw material for a weekly 10-minute video ("what I learned this week").

Group items that are about the same story. A later item may be the outcome, continuation or correction of an earlier
one; put them in one topic. For each topic:
- title: at most 10 words.
- hook: one plain sentence for a stranger, reflecting the LATEST state of the story (use the outcome if a later item
  has one).
- ids: every item id in the topic.
- status: ready (there is a result worth stating), developing (still open or running), weak (not worth airtime).
For a weak topic, keep the hook to a few words.
Order topics best first: what most local-LLM users would want to hear. Every id must appear in exactly one topic.
Answer with JSON only.

## ITEMS
{items}
"""

def load_window(path, days, now):
    since = (now - timedelta(days=days)).timestamp()
    rows = {}
    try:
        for ln in open(path):
            try: r = json.loads(ln)
            except ValueError: continue
            if r.get("ts", 0) >= since and r.get("source") != "test": rows[r["id"]] = r   # a re-run window replaces
    except FileNotFoundError: pass
    return sorted(rows.values(), key=lambda r: r["window"])

def call_model(host, prompt, timeout=900):
    body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": 12000, "temperature": 0.3,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {"name": "digest", "schema": SCHEMA}}}
    r = urllib.request.Request(host.rstrip("/") + "/v1/chat/completions", json.dumps(body).encode(),
                               {"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f: d = json.loads(f.read())
    ch = d["choices"][0]
    if ch.get("finish_reason") == "length": raise RuntimeError("hit max_tokens before finishing the JSON")
    return json.loads(ch["message"].get("content") or "").get("topics") or []

def validate(topics, rows):
    """Each id in exactly one topic; unknown ids dropped; anything the model left out becomes its own topic."""
    known, seen, out = {r["id"] for r in rows}, set(), []
    for t in topics:
        ids = []
        for i in t.get("ids") or []:
            if i in known and i not in seen and i not in ids: ids.append(i)
        if not ids: continue
        seen.update(ids); t["ids"] = ids; out.append(t)
    for r in rows:
        if r["id"] not in seen:
            out.append({"title": r["title"], "hook": r["hook"], "ids": [r["id"]], "talking_points": [],
                        "status": "developing", "unmerged": True})
    return out

_tracked = None
def link(ev):
    """Link evidence to the public repo only when the file is tracked there; anything else stays plain text."""
    global _tracked
    if _tracked is None:
        try: _tracked = subprocess.run(["git", "-C", ROOT, "ls-files", "data/receipts"], capture_output=True,
                                       text=True, timeout=30).stdout.split()
        except Exception: _tracked = []
    hits = [p for p in _tracked if p == ev or p.endswith("/" + ev.lstrip("./"))]
    return f"[{ev}]({GH}{hits[0]})" if len(hits) == 1 else f"`{ev}`"

def render(topics, rows, status, now, days):
    by = {r["id"]: r for r in rows}
    L = [f"# Content board -- {(now - timedelta(days=days)).strftime('%m-%d')} to {now.strftime('%m-%d')}", "",
         f"_{len(topics)} topics from {len(rows)} captures, digest {status}, generated {now.strftime('%Y-%m-%d %H:%M')} "
         "by tools/content_digest.py. **Hooks are model-written: check them before saying them.** "
         "Dates, numbers, quotes and evidence come from the hourly captures and were checked against the session "
         "text; a capture's context line is model-written too._", ""]
    order = {"ready": 0, "developing": 1, "weak": 2}
    main = [t for t in topics if t.get("status") != "weak"]
    main.sort(key=lambda t: order.get(t.get("status"), 1))   # stable: keeps the model's best-first order within status
    for n, t in enumerate(main, 1):
        mem = [by[i] for i in t["ids"]]
        kinds = sorted({m["kind"] for m in mem})
        L += [f"## {n}. {t['title']}", "",
              f"`{t.get('status')}` | {', '.join(kinds)} | audience {max(m['audience'] for m in mem)}/5 | "
              f"{len(mem)} capture{'s' * (len(mem) > 1)}{' | not merged by the model' * bool(t.get('unmerged'))}", "",
              f"**Hook (model):** {t['hook']}", ""]
        if t.get("talking_points"):
            L += ["**Talking points (model):**"] + [f"- {p}" for p in t["talking_points"]] + [""]
        L.append("**Timeline (captured):**")
        for m in sorted(mem, key=lambda m: m["window"]):
            bits = [f"- **{m['window']}** ({m['kind']}) {m['context']}"]
            if m.get("numbers"): bits.append(f"  - numbers: {'; '.join(m['numbers'])}")
            if m.get("quote"): bits.append(f"  - Mark: \"{m['quote']}\"")
            if m.get("evidence"): bits.append(f"  - evidence: {', '.join(link(e) for e in m['evidence'])}")
            if m.get("ungrounded_numbers"):
                bits.append(f"  - **check:** the model's prose has numbers not found in the session "
                            f"({', '.join(m['ungrounded_numbers'])})")
            L += bits
        L.append("")
    weak = [t for t in topics if t.get("status") == "weak"]
    if weak:
        L += ["## Not worth airtime (model's call)", ""]
        L += [f"- {t['title']} ({', '.join(by[i]['window'][:10] for i in t['ids'])})" for t in weak] + [""]
    return "\n".join(L)

def beat(status, **kw):
    row = {"ts": int(time.time()), "iso": datetime.now().isoformat(timespec="seconds"), "status": status, **kw}
    open(f"{CDIR}/.digest_heartbeat.json", "w").write(json.dumps(row) + "\n")
    with open(f"{CDIR}/.digest_beats.jsonl", "a") as f: f.write(json.dumps(row) + "\n")

def main(a):
    now = datetime.now()
    os.makedirs(CDIR, exist_ok=True)
    deny = load_deny(a.deny)
    rows = [r for r in load_window(a.candidates, a.days, now) if not denied(json.dumps(r, ensure_ascii=False), deny)]
    status, reason = "ok", ""
    if not rows:
        topics, status = [], "idle"
    else:
        items = "\n".join(json.dumps({k: r[k] for k in ("id", "window", "kind", "title", "hook", "context", "numbers",
                                                        "quote", "audience")}, ensure_ascii=False) for r in rows)
        try:
            topics = validate(call_model(a.host, PROMPT.replace("{items}", items)), rows)
            if any(denied(json.dumps(t, ensure_ascii=False), deny) for t in topics):
                raise RuntimeError("a model-written topic matched the deny list")
        except Exception as e:
            reason = f"{type(e).__name__}: {str(e)[:160]}"
            topics, status = validate([], rows), "degraded"
    sheet = render(topics, rows, status, now, a.days)
    out = a.out or f"{CDIR}/this_week.md"
    open(out, "w").write(sheet + "\n")
    if now.weekday() == 5 and not a.out:   # Saturday: keep the week's sheet
        open(f"{CDIR}/week_{now.strftime('%Y-%m-%d')}.md", "w").write(sheet + "\n")
    summ = {"status": status, "topics": len(topics), "captures": len(rows), "path": os.path.relpath(out, ROOT)}
    if reason: summ["reason"] = reason
    if not a.out: beat(**{**summ, "status": status})
    print(json.dumps(summ))
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://127.0.0.1:8099")
    p.add_argument("--candidates", default=f"{CDIR}/candidates.jsonl")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--deny", default=f"{CDIR}/private_terms.txt")
    p.add_argument("--out", help="write the sheet here instead (no heartbeat, no Saturday copy)")
    sys.exit(main(p.parse_args()))
