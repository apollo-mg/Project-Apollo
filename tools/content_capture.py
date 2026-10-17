#!/usr/bin/env python3
"""Hourly content capture: after the ledger writes a diary section, ask the same local model whether this window holds
anything worth telling other local-LLM users (a measured finding, a gotcha, a story, an opinion). Zero is the normal
answer. Candidates are appended to data/dev_diaries/content/candidates.jsonl, which is private (it quotes the session)
and gitignored; tools/content_digest.py merges, expands and ranks them nightly into content/this_week.md.

WHY hourly and not a weekly pass (Mark, 2026-10-17): a week later, the context that made something interesting in the
moment is gone unless it was written down, and a frequent capture lets the nightly pass judge whether an idea keeps
coming back or grows an outcome during the week.

Guards, because this file feeds public talking points:
- privacy: lines matching the deny list are dropped BEFORE the model sees them (so it cannot paraphrase around a term),
  and any candidate that still matches is dropped after. The list lives in content/private_terms.txt (gitignored);
  this code names nothing private. Generic patterns (emails, phone numbers, key-shaped strings) are built in.
- grounding: numbers, the quote and evidence paths must appear in the input; anything else is removed and counted.
  Model-written prose (hook, context) is kept but labelled as model text downstream.
- thinking off + a JSON schema (response_format), so the answer parses and no budget goes to reasoning.
- its own heartbeat (content/.capture_heartbeat.json + .capture_beats.jsonl). A failure here never changes the
  diary's beat; ledger_health.sh reports it.
"""
import argparse, json, os, re, sys, time, urllib.request
from datetime import datetime

ROOT = "/mnt/TG_2TB/Projects/Apollo"
CDIR = f"{ROOT}/data/dev_diaries/content"
KINDS = ["finding", "gotcha", "story", "opinion", "howto"]
SCHEMA = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "maxItems": 3, "items": {
    "type": "object",
    "required": ["title", "kind", "hook", "context", "numbers", "quote", "evidence", "audience"],
    "properties": {
        "title": {"type": "string"}, "kind": {"type": "string", "enum": KINDS},
        "hook": {"type": "string"}, "context": {"type": "string"},
        "numbers": {"type": "array", "maxItems": 6, "items": {"type": "string"}},
        "quote": {"type": "string"},
        "evidence": {"type": "array", "maxItems": 6, "items": {"type": "string"}},
        "audience": {"type": "integer", "minimum": 1, "maximum": 5}}}}}}

PROMPT = """You are scouting material for a weekly 10-minute video ("what I learned this week") and occasional posts by
a hobbyist who runs local LLMs on old datacenter GPUs and publishes measured results with the raw data. Below is one
window of his work session with an AI lab assistant (HUMAN = him, SAY = the assistant, ERR = a command that failed),
then the diary entry written for that window.

List 0 to 3 items worth telling OTHER local-LLM users about. Good items:
- a measured finding with a number (a speed, a score, a size, a before/after);
- a gotcha that would bite someone else (a flag, a tool's behaviour, a hardware or driver quirk) and what fixed it;
- a story with a surprise (a prediction that turned out wrong, a fix that wasn't, a model that beat expectations);
- an opinion HUMAN voiced about models, hardware or the field.
Not items: routine progress, moving files, commits, anything about business contacts, clients, employers, family,
health or money, credentials, or private conversations. Most windows have nothing; then return an empty list.

For each item:
- title: at most 10 words.
- kind: finding | gotcha | story | opinion | howto.
- hook: one plain sentence a stranger would care about.
- context: one or two sentences on what was being done and why it mattered at the time.
- numbers: measured values copied EXACTLY as they appear in the text below. Never compute, convert or round.
- quote: if HUMAN said something vivid about this item, copy it exactly; otherwise "".
- evidence: file names, commit ids or PR/issue references copied exactly from the text below; otherwise empty.
- audience: 1-5, how many local-LLM users this would interest or help.
Answer with JSON only.

## SESSION
{events}

## DIARY ENTRY
{diary}
"""

BUILTIN_DENY = [r"[\w.+-]+@[\w-]+\.[\w.]+",                     # email addresses
                r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b",          # phone numbers
                r"\b(?:hf|sk|ghp|gho|xox[bp])[_-][A-Za-z0-9]{16,}",  # key-shaped strings
                r"(?i)\bpass(?:word|wd)\b", r"(?i)\bapi[ _-]?key\b"]

def load_deny(path):
    pats = list(BUILTIN_DENY)
    try:
        for ln in open(path):
            ln = ln.strip()
            if not ln or ln.startswith("#"): continue
            pats.append(ln[3:] if ln.startswith("re:") else r"(?i)\b" + re.escape(ln) + r"\b")
    except FileNotFoundError:
        print(f"WARNING: no deny list at {path}; only the built-in patterns apply", file=sys.stderr)
    return [re.compile(p) for p in pats]

def denied(text, deny):
    return any(p.search(text) for p in deny)

def window_lines(events, deny, say_chars=400):
    """HUMAN, SAY and real failures; TOOL lines are actions, not material. Deny-listed lines never reach the model."""
    keep, n_denied = [], 0
    for ln in events:
        tag = ln[:6].strip()
        if tag not in ("HUMAN", "SAY", "ERR"): continue
        if tag == "ERR" and "[FAIL]" not in ln: continue
        if denied(ln, deny): n_denied += 1; continue
        keep.append(ln if tag == "HUMAN" else ln[:say_chars + 7])
    return keep, n_denied

def chunks(lines, max_chars=45000, max_chunks=4):
    """Split a long window instead of truncating it; past max_chunks, keep the latest."""
    out, cur, n = [], [], 0
    for ln in lines:
        if cur and n + len(ln) > max_chars: out.append(cur); cur, n = [], 0
        cur.append(ln[:max_chars]); n += len(ln) + 1
    if cur: out.append(cur)
    return out[-max_chunks:]

def last_section(diary_path, deny):
    """The section the ledger just appended (after the last '## HH:MM' header), skeleton block removed."""
    try: s = open(diary_path).read()
    except (FileNotFoundError, TypeError): return ""
    parts = re.split(r"(?m)^## \d\d:\d\d .*$", s)
    sec = re.sub(r"(?s)<details>.*?</details>", "", parts[-1] if len(parts) > 1 else "")
    paras = [p for p in re.split(r"\n\s*\n", sec) if p.strip() and not denied(p, deny)]
    return "\n\n".join(paras).strip()

def call_model(host, prompt, timeout=900):
    body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": 1500, "temperature": 0.3,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {"name": "content", "schema": SCHEMA}}}
    r = urllib.request.Request(host.rstrip("/") + "/v1/chat/completions", json.dumps(body).encode(),
                               {"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f: d = json.loads(f.read())
    ch = d["choices"][0]
    if ch.get("finish_reason") == "length": raise RuntimeError("hit max_tokens before finishing the JSON")
    return json.loads(ch["message"].get("content") or "")

NUM = re.compile(r"\d+(?:[.,]\d+)*")

def norm(s): return " ".join(s.split()).lower()

def ground(item, source, human):
    """Keep only what the input supports. Returns (item, n_removed)."""
    src, hum, src_nums = norm(source), norm(human), set(NUM.findall(source))
    removed = 0
    nums = []
    for n in item.get("numbers") or []:
        toks = NUM.findall(n)
        if norm(n) in src or (toks and all(t in src_nums for t in toks)): nums.append(n)
        else: removed += 1
    item["numbers"] = nums
    q = (item.get("quote") or "").strip().strip('"')
    if q and norm(q) not in hum: item["quote"] = ""; removed += 1
    else: item["quote"] = q
    ev = [e for e in item.get("evidence") or [] if norm(e) in src]
    removed += len(item.get("evidence") or []) - len(ev); item["evidence"] = ev
    # Numbers the model wrote into its own prose that appear nowhere in the input: flag, never silently trust.
    prose = " ".join([item.get("title", ""), item.get("hook", ""), item.get("context", "")])
    item["ungrounded_numbers"] = sorted({t for t in NUM.findall(prose) if len(t) > 1 and t not in src_nums})
    return item, removed

BEAT_DIR = CDIR

def beat(status, **kw):
    os.makedirs(BEAT_DIR, exist_ok=True)
    row = {"ts": int(time.time()), "iso": datetime.now().isoformat(timespec="seconds"), "status": status, **kw}
    line = json.dumps(row)
    open(f"{BEAT_DIR}/.capture_heartbeat.json", "w").write(line + "\n")
    with open(f"{BEAT_DIR}/.capture_beats.jsonl", "a") as f: f.write(line + "\n")
    print(line)

def capture(events, host, diary_text, window, source, deny, out, dry_run=False, max_chunks=4):
    lines, n_denied = window_lines(events, deny)
    if sum(len(x) for x in lines) < 200:
        return {"status": "idle", "window": window, "reason": "window too small", "denied_lines": n_denied}
    kept, n_private, n_removed, n_flagged, parts = [], 0, 0, 0, chunks(lines, max_chunks=max_chunks)
    for ci, part in enumerate(parts):
        text = "\n".join(part)
        human = "\n".join(ln for ln in part if ln.startswith("HUMAN"))
        prompt = PROMPT.replace("{events}", text).replace("{diary}", diary_text or "(none)")
        if dry_run:
            print(prompt); continue
        for i, it in enumerate((call_model(host, prompt).get("items") or [])[:3]):
            it = dict(it)
            if it.get("kind") not in KINDS: continue
            if denied(json.dumps(it, ensure_ascii=False), deny): n_private += 1; continue
            it, rm = ground(it, text + "\n" + (diary_text or ""), human)
            n_removed += rm; n_flagged += bool(it["ungrounded_numbers"])
            sfx = f"{ci}{i}" if len(parts) > 1 else f"{i}"
            it.update(id=f"c-{window.replace(' ', '-').replace(':', '')}-{sfx}", window=window, source=source,
                      ts=int(time.time()))
            kept.append(it)
    if dry_run: return {"status": "dry-run", "window": window}
    if kept:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "a") as f:
            for it in kept: f.write(json.dumps(it, ensure_ascii=False) + "\n")
            f.flush(); os.fsync(f.fileno())
    return {"status": "ok", "window": window, "chunks": len(parts), "items": len(kept), "dropped_private": n_private,
            "removed_ungrounded": n_removed, "flagged_prose_numbers": n_flagged, "denied_lines": n_denied}

def main(a):
    global BEAT_DIR
    BEAT_DIR = a.beat_dir
    deny = load_deny(a.deny)
    events = open(a.events, errors="replace").read().splitlines()
    window = a.window or datetime.now().strftime("%Y-%m-%d %H:%M")
    diary = last_section(a.diary, deny) if a.diary else ""
    try:
        res = capture(events, a.host, diary, window, a.source, deny, a.out, a.dry_run)
    except Exception as e:
        if not a.dry_run: beat("error", window=window, reason=f"{type(e).__name__}: {str(e)[:160]}")
        return 1
    if not a.dry_run: beat(res.pop("status"), **res)
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("events", help="ledger_extract.py output for this window")
    p.add_argument("--host", default="http://127.0.0.1:8099")
    p.add_argument("--diary", help="the day's ledger diary; its last section is used as context")
    p.add_argument("--window", help="label, default now (YYYY-MM-DD HH:MM)")
    p.add_argument("--source", default="hourly")
    p.add_argument("--deny", default=f"{CDIR}/private_terms.txt")
    p.add_argument("--out", default=f"{CDIR}/candidates.jsonl")
    p.add_argument("--beat-dir", default=CDIR, help="where the heartbeat goes (tests point this elsewhere)")
    p.add_argument("--dry-run", action="store_true", help="print the prompt; no model call, no writes")
    sys.exit(main(p.parse_args()))
