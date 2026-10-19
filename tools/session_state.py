#!/usr/bin/env python3
"""Session-state sidecar: keep a small, verified memory of a long Claude Code session, so a compaction loses words
but not facts.

WHY: Claude Code compacts a session by writing one fresh summary at a token threshold. Over this project's main
session that happened 88 times (2026-07-02 .. 10-19) and dropped ~55M tokens; what a summary does not carry comes back
only by grepping a 700 MB transcript blind. This tool treats compaction as INDEXING instead of summarising: a local
model reads each new slice of the transcript and writes short memory items, and every item points back to the exact
transcript lines it came from, so the verbatim text is one lookup away.

What the model writes is checked before it is kept (the model proposes, the code verifies):
  - every item must cite lines (L<n>) that were in the slice the model saw; an item with no valid citation is dropped;
  - a RULE must carry a quote that is literally present in one of the human lines it cites, else it is dropped;
  - numbers in an item's text that appear in none of its cited lines are marked [unverified];
  - deny-listed lines never reach the model, and an item that matches the deny list is dropped.

FILES (local only, outside the repo): ~/.local/share/apollo/session_state/<session-id>/
  cursor.json   byte offset + line number already processed      state.json  the memory items
  lines.json    line number -> byte offset, for cited lines        ops.jsonl   every proposed op, kept or not, and why
  state.md      the rendered state (what a post-compaction hook prints)

USAGE
  session_state.py update [--host URL] [--transcript T] [--max-chunks N]   # process new transcript lines
  session_state.py render [--budget CHARS]                                  # print state.md
  session_state.py lookup L123 L456                                         # verbatim transcript text for citations
  session_state.py replay --start-byte A --end-byte B --out DIR ...          # build a state from one slice (eval)
"""
import argparse, glob, json, os, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
sys.path.insert(0, str(ROOT / "tools"))
from ledger_extract import digest, classify_err, content_text      # same event grammar as the ledger
from content_capture import BUILTIN_DENY, denied

PROJ = Path.home() / ".claude/projects/-mnt-TG-2TB-Projects-Apollo"
BASE = Path.home() / ".local/share/apollo/session_state"
# Privacy filter. NOT content capture's list: that one is for PUBLIC posts and redacts ordinary work (engagement
# names, maintainers' names, personal projects), which a local state file needs. Here: secret-shaped strings, emails
# and phone numbers (content capture's first three built-ins), plus the personal categories Mark asked never to be
# stored (health, medical care, addiction, family), from a local list outside the repo.
PRIVATE_TERMS = BASE / "private_terms.txt"
KINDS = ["rule", "decision", "result", "task", "correction", "fact"]
NUM = re.compile(r"\d+(?:[.,]\d+)*")

SCHEMA = {"type": "object", "required": ["ops"], "properties": {"ops": {"type": "array", "maxItems": 24, "items": {
    "type": "object", "required": ["op", "kind", "text", "refs"], "properties": {
        "op": {"type": "string", "enum": ["ADD", "UPDATE", "DELETE"]},
        "id": {"type": "string"},
        "kind": {"type": "string", "enum": KINDS},
        "text": {"type": "string"},
        "quote": {"type": "string"},
        "status": {"type": "string", "enum": ["open", "done", "dropped", "none"]},
        "refs": {"type": "array", "items": {"type": "string"}, "maxItems": 6}}}}}}

PROMPT = """You maintain the long-term working memory of a software and hardware research session between a human (Mark)
and an AI agent. A future agent will lose this conversation and keep only your memory. Write what it needs in order to
act correctly: the rules Mark set, what was decided and why, results with their numbers, open tasks, and corrections.

Each event line starts with a citation like L123. HUMAN = Mark's words, SAY = the agent's words, TOOL = an action taken,
ERR = a failure.

Return JSON operations against the existing memory:
- ADD a new item. UPDATE an existing item by its id when new events change it (a task finished, a number corrected).
  DELETE an item by its id only when the events show it is wrong or no longer applies.
- kind: rule (a standing instruction or constraint from Mark), decision (what was chosen, and why), result (a measured
  finding, with its numbers), task (work still to do or just finished; set status), correction (something earlier
  that turned out wrong, and what is right), fact (a durable fact about the setup: hosts, paths, versions, ports).
- text: ONE fact per item, at most 50 words, self-contained. Its subject is the thing or the decision, not "the user"
  or "the agent". Keep exact names, paths, commands, error strings and numbers. No narration ("the session
  continued..."). Several facts make several items.
- quote: for a rule, copy a short phrase of Mark's exact words from the HUMAN line you cite, character for character.
  A rule without such a quote is discarded. Optional for other kinds.
- refs: the L-numbers of the lines that support the item (1 to 6). Never invent a citation.
- Skip chit-chat, greetings, and anything already in memory unchanged. Fewer, denser items are better.
- Never record anything about health, medical care, addiction, family members, relationships, money or personal life,
  even if it appears. Never record passwords, keys or tokens.

EXISTING MEMORY (id | kind | text):
{memory}

NEW EVENTS:
{events}
"""


def norm(s):
    return " ".join(s.split()).lower()


# ---------------------------------------------------------------- transcript -> events with citations
def events_from(transcript, start_byte=0, start_line=0, end_byte=None):
    """Yield (line_no, byte_offset, tag, text) for one transcript slice, plus the final (byte, line) cursor."""
    uses, out = {}, []
    off, ln = start_byte, start_line
    with open(transcript, "rb") as f:
        f.seek(start_byte)
        for raw in f:
            if end_byte is not None and off >= end_byte: break
            here, off, ln = off, off + len(raw), ln + 1
            if not raw.endswith(b"\n"):                      # a line still being written: stop before it
                off, ln = here, ln - 1; break
            try: d = json.loads(raw)
            except Exception: continue
            t = d.get("type")
            if t not in ("user", "assistant") or d.get("isCompactSummary") or d.get("isMeta"): continue
            content = (d.get("message") or {}).get("content")
            L = ln - 1                                       # 0-based line number, as `sed -n` would need +1
            if isinstance(content, str):
                if t == "user" and not content.startswith("<"): out.append((L, here, "HUMAN", content))
                continue
            if not isinstance(content, list): continue
            for b in content:
                if not isinstance(b, dict): continue
                bt = b.get("type")
                if bt == "text":
                    txt = (b.get("text") or "").strip()
                    if not txt or (t == "user" and txt.startswith("<")): continue
                    out.append((L, here, "SAY" if t == "assistant" else "HUMAN", txt))
                elif bt == "tool_use":
                    inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                    uses[b.get("id")] = (b.get("name", "?"), str(inp.get("command", "")))
                    out.append((L, here, "TOOL", f"{b.get('name', '?')}  {digest(b.get('name'), inp, 300)}"))
                elif bt == "tool_result" and b.get("is_error"):
                    s = content_text(b.get("content"))
                    name, cmd = uses.get(b.get("tool_use_id"), ("?", ""))
                    if classify_err(s, cmd) == "FAIL":
                        out.append((L, here, "ERR", f"{name}: {' '.join(s.split())[:200]}"))
    return out, off, ln


SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def redact(text, deny):
    """Drop deny-listed SENTENCES, not whole messages: Mark often puts a personal aside and a work instruction in one
    message, and dropping the message would lose the instruction. Returns (text, n_sentences_dropped)."""
    flat = " ".join(text.split())
    if not denied(flat, deny): return flat, 0
    keep, n = [], 0
    for snt in SENT.split(flat):
        if denied(snt, deny): n += 1
        else: keep.append(snt)
    return (" ".join(keep) + " [redacted]").strip() if keep else "", n


def pieces(flat, cap):
    """Split a long message into <= cap-char pieces at sentence ends, so its later sentences (often the numbers of a
    result) are kept instead of cut off. A single over-long sentence is hard-cut."""
    out, cur = [], ""
    for snt in SENT.split(flat):
        while len(snt) > cap: out.append(snt[:cap]); snt = snt[cap:]
        if cur and len(cur) + 1 + len(snt) > cap: out.append(cur); cur = snt
        else: cur = (cur + " " + snt).strip()
    if cur: out.append(cur)
    return out


def render_events(evs, deny, say_chars=1200, max_pieces=6):
    """Event lines for the prompt, redacted before any model sees them. HUMAN and SAY messages longer than say_chars
    become several lines with the same citation (at most max_pieces); a TOOL line is one 300-char digest.
    Returns (lines, n_redacted, visible_text_by_line)."""
    lines, n_denied, visible = [], 0, {}
    for L, _, tag, txt in evs:
        flat, n = redact(txt, deny)
        n_denied += n
        if not flat: continue
        parts = pieces(flat, say_chars)[:max_pieces] if tag in ("HUMAN", "SAY") else [flat[:300]]
        for part in parts: lines.append(f"L{L} {tag:<5} {part}")
        prev = visible.get(L, (tag, ""))
        visible[L] = (prev[0], (prev[1] + " " + " ".join(parts)).strip())
    return lines, n_denied, visible


def chunks(lines, max_chars):
    out, cur, n = [], [], 0
    for x in lines:
        if cur and n + len(x) > max_chars: out.append(cur); cur, n = [], 0
        cur.append(x); n += len(x) + 1
    if cur: out.append(cur)
    return out


# ---------------------------------------------------------------- model call
def call_model(host, prompt, template_kwargs, max_tokens=3000, timeout=1800):
    body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.0,
            "cache_prompt": False, "chat_template_kwargs": template_kwargs,
            "response_format": {"type": "json_schema", "json_schema": {"name": "memory_ops", "schema": SCHEMA}}}
    req = urllib.request.Request(host.rstrip("/") + "/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as f: d = json.loads(f.read())
    ch = d["choices"][0]
    content = ch["message"].get("content") or ""
    if ch.get("finish_reason") == "length": raise RuntimeError("hit max_tokens before finishing the JSON")
    if not content.strip(): raise RuntimeError("empty content (thinking ate the budget?)")
    return json.loads(content), {"s": round(time.time() - t0, 1), "usage": d.get("usage", {})}


# ---------------------------------------------------------------- verification + apply
def apply_ops(state, ops, chunk_text_by_line, deny, log):
    """Verify each proposed op against the slice the model saw; apply what survives. Returns counts."""
    items, kept, dropped = state["items"], 0, 0
    for op in ops:
        why = None
        kind, text = op.get("kind"), " ".join((op.get("text") or "").split())
        refs = []
        for r in op.get("refs") or []:
            m = re.fullmatch(r"L?(\d+)", str(r).strip())
            if m and int(m.group(1)) in chunk_text_by_line: refs.append(int(m.group(1)))
        cited = " ".join(chunk_text_by_line[r][1] for r in refs)
        human = " ".join(chunk_text_by_line[r][1] for r in refs if chunk_text_by_line[r][0] == "HUMAN")
        quote = " ".join((op.get("quote") or "").split()).strip('"')
        if op.get("op") in ("UPDATE", "DELETE") and op.get("id") not in items: why = "unknown id"
        elif op.get("op") != "DELETE" and not text: why = "empty text"
        elif not refs: why = "no valid citation"
        elif denied(text + " " + quote, deny): why = "deny list"
        if why is None and quote and norm(quote) not in norm(human):
            if kind == "rule": why = "rule quote not in cited human lines"
            else: quote = ""
        if why is None and kind == "rule" and not quote: why = "rule without a verified quote"
        log.append({"op": op, "kept": why is None, "why": why, "refs_valid": refs})
        if why: dropped += 1; continue
        unverified = [n for n in NUM.findall(text) if len(n) > 1 and n not in cited]
        rec = {"kind": kind, "text": text, "quote": quote, "refs": refs, "status": op.get("status") or "none",
               "unverified": unverified, "t": int(time.time())}
        if op["op"] == "ADD":
            iid = f"m{state['next_id']}"; state["next_id"] += 1; items[iid] = rec
        elif op["op"] == "UPDATE":
            old = items[op["id"]]; rec["refs"] = sorted(set(old["refs"]) | set(refs))[-8:]
            if not rec["quote"]: rec["quote"] = old.get("quote", "")
            items[op["id"]] = rec
        else:
            items.pop(op["id"], None)
        kept += 1
    return kept, dropped


def memory_lines(state, limit=200):
    its = sorted(state["items"].items(), key=lambda kv: kv[1]["t"])[-limit:]
    return "\n".join(f"{i} | {r['kind']}{'/' + r['status'] if r['kind'] == 'task' else ''} | {r['text']}"
                     for i, r in its) or "(empty)"


def render(state, budget=24000):
    """Markdown for re-injection after a compaction: rules and open tasks first, then the newest of the rest."""
    its = state["items"]
    def line(i, r):
        q = f' -- "{r["quote"]}"' if r.get("quote") and r["kind"] == "rule" else ""
        u = f" [unverified: {', '.join(r['unverified'])}]" if r.get("unverified") else ""
        return f"- {r['text']}{q}{u} ({', '.join('L%d' % x for x in r['refs'])})"
    # Under a tight budget the later sections are cut first: results (numbers) outrank decisions on purpose.
    order = [("Rules Mark set", lambda r: r["kind"] == "rule"),
             ("Open tasks", lambda r: r["kind"] == "task" and r["status"] == "open"),
             ("Corrections", lambda r: r["kind"] == "correction"),
             ("Results", lambda r: r["kind"] == "result"),
             ("Decisions", lambda r: r["kind"] == "decision"),
             ("Facts", lambda r: r["kind"] == "fact"),
             ("Finished tasks", lambda r: r["kind"] == "task" and r["status"] != "open")]
    out = ["# Session state (local sidecar; verify before acting)",
           "Citations are transcript lines: `tools/session_state.py lookup L<n>` prints the verbatim text."]
    used = sum(len(x) + 1 for x in out)
    for title, pred in order:
        sel = sorted(((i, r) for i, r in its.items() if pred(r)), key=lambda kv: -kv[1]["t"])
        if not sel: continue
        block = [f"\n## {title}"]
        for i, r in sel:
            s = line(i, r)
            if used + len(s) + 1 > budget: break
            block.append(s); used += len(s) + 1
        if len(block) > 1: out += block
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- commands
def latest_transcript():
    ts = sorted(glob.glob(str(PROJ / "*.jsonl")), key=os.path.getmtime)
    if not ts: sys.exit("no transcript under " + str(PROJ))
    return ts[-1]


def load_json(p, default):
    try: return json.load(open(p))
    except FileNotFoundError: return default


def save_json(p, obj):
    tmp = str(p) + ".tmp"
    with open(tmp, "w") as f: json.dump(obj, f, indent=1); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)


def run_slice(transcript, sdir, start_byte, start_line, end_byte, a):
    """Process one slice into the state in sdir, chunk by chunk, persisting after every chunk."""
    sdir.mkdir(parents=True, exist_ok=True)
    deny = deny_patterns()
    state = load_json(sdir / "state.json", {"items": {}, "next_id": 1})
    index = load_json(sdir / "lines.json", {})
    evs, off, ln = events_from(transcript, start_byte, start_line, end_byte)
    lines, n_denied, by_line = render_events(evs, deny)   # verification sees only what the model saw
    for L, here, _, _ in evs: index[str(L)] = here
    cks = chunks(lines, a.chunk_chars)
    if a.max_chunks and len(cks) > a.max_chunks: cks = cks[-a.max_chunks:]
    tk = json.loads(a.template_kwargs)
    stats = {"events": len(evs), "denied": n_denied, "chunks": len(cks), "kept": 0, "dropped": 0, "calls": []}
    with open(sdir / "ops.jsonl", "a") as oplog:
        for ck in cks:
            seen = {int(x.split(" ", 1)[0][1:]) for x in ck}
            view = {L: by_line[L] for L in seen if L in by_line}
            prompt = PROMPT.replace("{memory}", memory_lines(state)).replace("{events}", "\n".join(ck))
            if a.dry_run: print(prompt); return stats
            res, meta = call_model(a.host, prompt, tk)
            if getattr(a, "save_io", False):      # eval: keep exact prompts/outputs for cross-quant agreement
                with open(sdir / "io.jsonl", "a") as io:
                    io.write(json.dumps({"prompt": prompt, "response": res, **meta}) + "\n")
            log = []
            k, d = apply_ops(state, res.get("ops") or [], view, deny, log)
            stats["kept"] += k; stats["dropped"] += d; stats["calls"].append(meta)
            for rec in log: oplog.write(json.dumps({"t": int(time.time()), **rec}) + "\n")
            oplog.flush()
            save_json(sdir / "state.json", state); save_json(sdir / "lines.json", index)
    (sdir / "state.md").write_text(render(state, a.budget))
    return stats, off, ln


def deny_patterns():
    pats = [re.compile(p) for p in BUILTIN_DENY[:3]]
    if PRIVATE_TERMS.exists(): pats += _extra(PRIVATE_TERMS)
    else: print(f"WARNING: no {PRIVATE_TERMS}; only secret/email/phone patterns apply", file=sys.stderr)
    return pats


def _extra(path):
    """Session deny terms (local file), same format as content capture's list: a term per line, or re:<regex>."""
    pats = []
    for l in open(path):
        l = l.strip()
        if not l or l.startswith("#"): continue
        pats.append(re.compile(l[3:] if l.startswith("re:") else r"(?i)\b" + re.escape(l) + r"\b"))
    return pats


def cmd_update(a):
    t = a.transcript or latest_transcript()
    sid = Path(t).stem
    sdir = BASE / sid
    cur = load_json(sdir / "cursor.json", None)
    if cur is None:   # first run on a session: start from the last compaction boundary, not from July
        cur = {"byte": last_boundary(t), "line": None}
    if cur["line"] is None:
        cur["line"] = count_lines(t, cur["byte"])
    out = run_slice(t, sdir, cur["byte"], cur["line"], None, a)
    if a.dry_run: return
    stats, off, ln = out
    save_json(sdir / "cursor.json", {"byte": off, "line": ln, "transcript": t})
    beat = {"ts": int(time.time()), "status": "ok", **{k: v for k, v in stats.items() if k != "calls"},
            "secs": sum(c["s"] for c in stats["calls"]), "host": a.host}
    save_json(sdir / "heartbeat.json", beat)
    print(json.dumps(beat))


def cmd_replay(a):
    """Eval helper: build a fresh state from one byte range of a transcript into --out."""
    out = Path(a.out)
    if (out / "state.json").exists() and not a.resume: sys.exit(f"{out} already has a state; pass --resume")
    stats, off, ln = run_slice(a.transcript, out, a.start_byte, count_lines(a.transcript, a.start_byte), a.end_byte, a)
    save_json(out / "replay.json", {"transcript": a.transcript, "start_byte": a.start_byte, "end_byte": a.end_byte,
                                    "host": a.host, "template_kwargs": a.template_kwargs, "budget": a.budget,
                                    "chunk_chars": a.chunk_chars, **stats})
    print(json.dumps({k: v for k, v in stats.items() if k != "calls"}))


def last_boundary(t):
    """Byte offset of the newest compaction boundary in the transcript (0 if none)."""
    off, best = 0, 0
    with open(t, "rb") as f:
        for raw in f:
            if b'"compact_boundary"' in raw: best = off
            off += len(raw)
    return best


def count_lines(t, byte):
    n = 0
    with open(t, "rb") as f:
        while f.tell() < byte:
            chunk = f.read(min(1 << 24, byte - f.tell()))
            if not chunk: break
            n += chunk.count(b"\n")
    return n


def cmd_render(a):
    sdir = BASE / Path(a.transcript or latest_transcript()).stem
    st = load_json(sdir / "state.json", None)
    if st is None: return
    sys.stdout.write(render(st, a.budget))


def cmd_lookup(a):
    t = a.transcript or latest_transcript()
    sdir = Path(a.state_dir) if a.state_dir else BASE / Path(t).stem
    index = load_json(sdir / "lines.json", {})
    with open(t, "rb") as f:
        for ref in a.refs:
            L = int(ref.lstrip("Ll"))
            if str(L) not in index: print(f"L{L}: not indexed"); continue
            f.seek(index[str(L)]); d = json.loads(f.readline())
            c = (d.get("message") or {}).get("content")
            if isinstance(c, list):
                c = "\n".join(b.get("text") or json.dumps(b.get("input", ""))[:2000] for b in c if isinstance(b, dict)
                              and b.get("type") in ("text", "tool_use"))
            print(f"=== L{L} {d.get('type')} {d.get('timestamp', '')}\n{c}\n")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    def common(q):
        q.add_argument("--transcript")
        q.add_argument("--host", default="http://127.0.0.1:8099")
        q.add_argument("--template-kwargs", default='{"enable_thinking": false}')
        q.add_argument("--chunk-chars", type=int, default=40000)
        q.add_argument("--max-chunks", type=int, default=0)
        q.add_argument("--budget", type=int, default=24000)
        q.add_argument("--dry-run", action="store_true")
    q = sub.add_parser("update"); common(q); q.set_defaults(f=cmd_update)
    q = sub.add_parser("replay"); common(q); q.set_defaults(f=cmd_replay)
    q.add_argument("--start-byte", type=int, required=True); q.add_argument("--end-byte", type=int, required=True)
    q.add_argument("--out", required=True); q.add_argument("--resume", action="store_true")
    q.add_argument("--save-io", action="store_true", help="also write io.jsonl: every prompt and parsed response")
    q = sub.add_parser("render"); q.add_argument("--transcript"); q.add_argument("--budget", type=int, default=24000)
    q.set_defaults(f=cmd_render)
    q = sub.add_parser("lookup"); q.add_argument("refs", nargs="+"); q.add_argument("--transcript")
    q.add_argument("--state-dir"); q.set_defaults(f=cmd_lookup)
    a = p.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
