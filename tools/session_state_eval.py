#!/usr/bin/env python3
"""Evaluate session-state writers against Claude Code's own compaction summaries (PREREG_SESSION_STATE.md).

A compaction SEGMENT k is the transcript between compaction boundary k-1 and boundary k; Claude Code's summary k is
written at boundary k and must carry segment k forward (plus summary k-1, which was in context). Each arm produces a
text for segment k; the text is scored on how many of segment k's GOLD items it still carries.

GOLD (mechanical, chosen by no writer and by no judge):
  commit     subject of each commit made in the segment's time window with a Claude co-author trailer
  directive  a sentence of Mark's (HUMAN line) matching the directive regex below
  memory     the description (Write) or first sentences (heredoc append) of each memory file written in the segment
Each item gets KEY TOKENS (numbers, file/path/identifier-shaped tokens, hashes). An item is CARRIED by a text when at
least half its keys occur in it, as whole tokens. Items with fewer than 2 keys are not scored (counted only). Items that
match the personal deny list are excluded: the sidecar is meant not to keep them.

Everything this writes stays LOCAL (EVAL dir, outside the repo): gold, arm texts and per-item scores contain private
session content. Only aggregate numbers are copied into data/receipts/.

  session_state_eval.py segments                 # list boundaries, assert summary mapping, write segments.json
  session_state_eval.py gold                     # build gold.json for the registered segments
  session_state_eval.py arm-inc | arm-ext        # incumbent summaries / extractive baseline
  session_state_eval.py arm-writer --name HY4 --host URL --template-kwargs JSON   # run a writer over every segment
  session_state_eval.py agree --a HY8 --b-host URL --template-kwargs JSON         # same prompts, another model
  session_state_eval.py score                    # all arms x budgets, chance control -> results.json
"""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
sys.path.insert(0, str(ROOT / "tools"))
import session_state as S

T = str(Path.home() / ".claude/projects/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912.jsonl")
EVAL = Path.home() / ".local/share/apollo/session_state_eval"
SEGS = list(range(75, 88))           # registered: boundaries 75..87 (88 = the live slice, used as dev, never scored)
BUDGETS = (0.5, 1.0, 2.0)            # x the incumbent summary's length, per segment
MEMDIR = "/.claude/projects/-mnt-TG-2TB-Projects-Apollo/memory/"
DIRECTIVE = re.compile(r"(?i)\b(never|always|don'?t|do not|make sure|from now on|remember|keep|stop|avoid|"
                       r"go ahead|let'?s|please|I want|we should|you should|must)\b")
KEY = re.compile(r"(?<![\w])(?:[0-9a-f]{7,12}(?=[^\w]|$)|\d+(?:\.\d+)+x?|\d{2,}(?:x|%)?|[A-Za-z][\w-]*[_/.][\w./-]*\w|"
                 r"[A-Z][A-Z0-9]{2,}(?:_[A-Z0-9]+)*|[a-z]+[A-Z]\w+)")
YEAR = re.compile(r"^20\d\d$")
# Generic words that would match almost any text about this project; dropped from keys (registered list).
STOP = {"result", "results", "prereg", "addendum", "deviation", "gpu", "gpus", "cpu", "ram", "vram", "pass", "fail",
        "gate", "json", "api", "url", "http", "https", "todo", "note", "md", "py", "ok", "pr"}
# A HUMAN sentence that is a paste of someone else's chat or a web page is not Mark's directive.
PASTE = re.compile(r"\b\d{1,2}:\d{2}\s?[AP]M\b|Hugging Face We|\u2014\s*\d{1,2}:\d{2}|\[[A-Z]{2,5}\],")
MARKERS = re.compile(r"\((?:L\d+(?:, )?)+\)|\[unverified:[^\]]*\]|`tools/session_state\.py lookup L<n>`")


def load(p, d=None):
    try: return json.load(open(p))
    except FileNotFoundError: return d


def save(p, o):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p) + ".tmp"
    with open(tmp, "w") as f: json.dump(o, f, indent=1); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)


# ---------------------------------------------------------------- segments
def cmd_segments(a):
    bounds, summ, off = [], [], 0
    with open(T, "rb") as f:
        for raw in f:
            if b'"compact_boundary"' in raw or b'"isCompactSummary"' in raw:
                d = json.loads(raw)
                if d.get("type") == "system" and d.get("subtype") == "compact_boundary":
                    bounds.append({"byte": off, "ts": d["timestamp"], "pre": (d.get("compactMetadata") or {}).get("preTokens"),
                                   "trigger": (d.get("compactMetadata") or {}).get("trigger")})
                elif d.get("isCompactSummary"):
                    c = (d.get("message") or {}).get("content")
                    txt = c if isinstance(c, str) else "\n".join(b.get("text", "") for b in c if isinstance(b, dict))
                    summ.append({"byte": off, "ts": d["timestamp"], "text": txt})
            off += len(raw)
    assert len(bounds) == len(summ), (len(bounds), len(summ))
    segs = []
    for k, (b, s) in enumerate(zip(bounds, summ)):
        dt = abs(_ts(b["ts"]) - _ts(s["ts"]))
        assert s["byte"] > b["byte"] and dt < 5, f"summary {k} does not follow boundary {k} ({dt}s)"
        if k == 0: continue
        segs.append({"k": k, "start": bounds[k - 1]["byte"], "end": b["byte"], "t0": bounds[k - 1]["ts"], "t1": b["ts"],
                     "pre_tokens": b["pre"], "trigger": b["trigger"], "summary_chars": len(s["text"])})
        save(EVAL / "inc" / f"seg{k}.txt", {"text": s["text"]}) if a.write_inc else None
    save(EVAL / "segments.json", segs)
    for s in segs[-14:]: print(s["k"], s["t1"][:16], s["trigger"], s["pre_tokens"], round((s["end"] - s["start"]) / 1e6, 1), "MB", s["summary_chars"], "chars")


def _ts(iso):
    from datetime import datetime
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


# ---------------------------------------------------------------- gold
def keys_of(text):
    out = []
    for m in KEY.findall(text):
        k = m.lower().rstrip(".,;:")
        if YEAR.match(k) or len(k) < 2 or k in STOP: continue
        if k not in out: out.append(k)
    return out


def cmd_gold(a):
    segs = {s["k"]: s for s in load(EVAL / "segments.json")}
    deny = S.deny_patterns()
    gold = {}
    for k in SEGS:
        s, items = segs[k], []
        # commits with a Claude co-author trailer in the window
        log = subprocess.run(["git", "-C", str(ROOT), "log", f"--since={s['t0']}", f"--until={s['t1']}",
                              "--format=%H%x1f%s%x1f%b%x1e"], capture_output=True, text=True).stdout
        for rec in log.split("\x1e"):
            parts = rec.strip("\n").split("\x1f")
            if len(parts) < 3 or "Co-Authored-By: Claude" not in parts[2]: continue
            items.append({"src": "commit", "id": parts[0][:10], "text": parts[1]})
        evs, _, _ = S.events_from(T, s["start"], 0, s["end"])
        for L, _, tag, txt in evs:
            if tag != "HUMAN": continue
            for snt in S.SENT.split(" ".join(txt.split())):
                if DIRECTIVE.search(snt) and 20 <= len(snt) <= 600 and not PASTE.search(txt):
                    items.append({"src": "directive", "id": f"L{L}", "text": snt})
        items += memory_writes(s)
        for it in items:
            it["keys"] = keys_of(it["text"])
            it["excluded"] = "deny" if S.denied(it["text"], deny) else ("few_keys" if len(it["keys"]) < 2 else None)
        gold[k] = items
        n = [i for i in items if not i["excluded"]]
        print(k, "items", len(items), "scored", len(n), {src: sum(1 for i in n if i["src"] == src) for src in ("commit", "directive", "memory")})
    save(EVAL / "gold.json", gold)


def memory_writes(s):
    out = []
    with open(T, "rb") as f:
        f.seek(s["start"])
        off = s["start"]
        for raw in f:
            if off >= s["end"]: break
            off += len(raw)
            if MEMDIR.encode() not in raw or b'"tool_use"' not in raw: continue
            d = json.loads(raw)
            for b in (d.get("message") or {}).get("content") or []:
                if not isinstance(b, dict) or b.get("type") != "tool_use": continue
                inp = b.get("input") or {}
                fp, cmd = str(inp.get("file_path", "")), str(inp.get("command", ""))
                if b.get("name") == "Write" and MEMDIR in fp and not fp.endswith("MEMORY.md"):
                    m = re.search(r"(?m)^description:\s*(.+)$", inp.get("content", ""))
                    if m: out.append({"src": "memory", "id": Path(fp).stem, "text": m.group(1)})
                elif b.get("name") == "Bash" and MEMDIR in cmd and "<<" in cmd and "MEMORY.md" not in cmd.split("<<")[0]:
                    body = cmd.split("\n", 1)[1] if "\n" in cmd else ""
                    body = body.rsplit("EOF", 1)[0]
                    sents = S.SENT.split(" ".join(body.split()))
                    txt = " ".join(sents[:3])[:600]
                    if txt: out.append({"src": "memory", "id": "append", "text": txt})
    return out


# ---------------------------------------------------------------- arms
def cmd_arm_inc(a):
    for k in SEGS:
        assert (EVAL / "inc" / f"seg{k}.txt").exists(), "run: segments --write-inc"
    print("INC texts in", EVAL / "inc")


def cmd_arm_ext(a):
    """No-model control: the newest redacted HUMAN and SAY lines of the segment, cut to the budget (newest kept)."""
    segs = {s["k"]: s for s in load(EVAL / "segments.json")}
    deny = S.deny_patterns()
    for k in SEGS:
        evs, _, _ = S.events_from(T, segs[k]["start"], 0, segs[k]["end"])
        lines, _, _ = S.render_events([e for e in evs if e[2] in ("HUMAN", "SAY")], deny)
        save(EVAL / "ext" / f"seg{k}.json", {"lines": [re.sub(r"^L\d+ ", "", x) for x in lines]})
    print("EXT lines in", EVAL / "ext")


def cmd_arm_writer(a):
    segs = {s["k"]: s for s in load(EVAL / "segments.json")}
    for k in SEGS:
        out = EVAL / a.name / f"seg{k}"
        if (out / "replay.json").exists(): print(k, "done"); continue
        if out.exists(): subprocess.run(["rm", "-rf", str(out)])   # a partial state from an interrupted run
        cmd = [sys.executable, str(ROOT / "tools/session_state.py"), "replay", "--transcript", T,
               "--start-byte", str(segs[k]["start"]), "--end-byte", str(segs[k]["end"]), "--out", str(out),
               "--host", a.host, "--template-kwargs", a.template_kwargs, "--save-io"]
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(k, round(time.time() - t0), "s", r.stdout.strip()[-200:], r.stderr.strip()[-300:], flush=True)
        if r.returncode: sys.exit(f"segment {k} failed")


def text_of(arm, k, budget_chars):
    if arm == "INC": return load(EVAL / "inc" / f"seg{k}.txt")["text"]
    if arm == "EXT":
        lines, out, n = load(EVAL / "ext" / f"seg{k}.json")["lines"], [], 0
        for x in reversed(lines):
            if n + len(x) + 1 > budget_chars: break
            out.append(x); n += len(x) + 1
        return "\n".join(reversed(out))
    st = load(EVAL / arm / f"seg{k}" / "state.json")
    return S.render(st, budget_chars) if st else ""


def carried(item, text_l):
    hits = sum(1 for key in item["keys"] if re.search(r"(?<![\w.])" + re.escape(key) + r"(?![\w])", text_l))
    return hits, hits * 2 >= len(item["keys"])


def cmd_score(a):
    segs = {s["k"]: s for s in load(EVAL / "segments.json")}
    gold = {int(k): v for k, v in load(EVAL / "gold.json").items()}
    arms = ["INC", "EXT"] + [d.name for d in EVAL.iterdir() if d.is_dir() and d.name not in ("inc", "ext")]
    res, per_item = {}, {}
    for arm in arms:
        for mult in BUDGETS:
            if arm == "INC" and mult != 1.0: continue
            tot = {"n": 0, "carried": 0, "chance_n": 0, "chance_carried": 0, "by_src": {}}
            for k in SEGS:
                if arm not in ("INC", "EXT") and not (EVAL / arm / f"seg{k}" / "state.json").exists(): continue
                text = text_of(arm, k, int(segs[k]["summary_chars"] * mult))
                text_l = MARKERS.sub(" ", text).lower()
                j = SEGS[SEGS.index(k) + 1] if k != SEGS[-1] else SEGS[0]     # chance control: another segment's gold
                for it in gold[k]:
                    if it["excluded"]: continue
                    _, ok = carried(it, text_l)
                    tot["n"] += 1; tot["carried"] += ok
                    b = tot["by_src"].setdefault(it["src"], [0, 0]); b[0] += 1; b[1] += ok
                    per_item.setdefault(f"{arm}@{mult}", []).append({"k": k, "src": it["src"], "id": it["id"], "ok": ok})
                for it in gold[j]:
                    if it["excluded"]: continue
                    tot["chance_n"] += 1; tot["chance_carried"] += carried(it, text_l)[1]
            if tot["n"]:
                res[f"{arm}@{mult}"] = {"recall": round(tot["carried"] / tot["n"], 3), "n": tot["n"],
                                        "chance": round(tot["chance_carried"] / max(1, tot["chance_n"]), 3),
                                        "by_src": {s_: round(v[1] / v[0], 3) for s_, v in tot["by_src"].items()},
                                        "by_src_n": {s_: v[0] for s_, v in tot["by_src"].items()}}
    save(EVAL / "results.json", res); save(EVAL / "per_item.json", per_item)
    for k_, v in sorted(res.items(), key=lambda kv: -kv[1]["recall"]): print(f"{k_:12s} recall {v['recall']:.3f}  chance {v['chance']:.3f}  n={v['n']}  {v['by_src']}")


def cmd_agree(a):
    """Send the exact prompts arm A's writer saw to another server; compare outputs op by op."""
    rows = []
    for k in SEGS:
        io = EVAL / a.a / f"seg{k}" / "io.jsonl"
        if not io.exists(): continue
        for i, l in enumerate(open(io)):
            r = json.loads(l)
            other, meta = S.call_model(a.b_host, r["prompt"], json.loads(a.template_kwargs))
            A = [(o.get("op"), o.get("kind"), " ".join((o.get("text") or "").split())) for o in r["response"].get("ops") or []]
            B = [(o.get("op"), o.get("kind"), " ".join((o.get("text") or "").split())) for o in other.get("ops") or []]
            ta, tb = set(" ".join(x[2] for x in A).lower().split()), set(" ".join(x[2] for x in B).lower().split())
            rows.append({"k": k, "i": i, "identical": A == B, "n_a": len(A), "n_b": len(B),
                         "word_jaccard": round(len(ta & tb) / max(1, len(ta | tb)), 3), "b_s": meta["s"], "b_out": other})
            print(k, i, rows[-1]["identical"], rows[-1]["n_a"], rows[-1]["n_b"], rows[-1]["word_jaccard"], flush=True)
            save(EVAL / f"agree_{a.a}_vs_{a.b_name}.json", rows)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("segments"); q.add_argument("--write-inc", action="store_true"); q.set_defaults(f=cmd_segments)
    sub.add_parser("gold").set_defaults(f=cmd_gold)
    sub.add_parser("arm-inc").set_defaults(f=cmd_arm_inc)
    sub.add_parser("arm-ext").set_defaults(f=cmd_arm_ext)
    q = sub.add_parser("arm-writer"); q.add_argument("--name", required=True); q.add_argument("--host", required=True)
    q.add_argument("--template-kwargs", required=True); q.set_defaults(f=cmd_arm_writer)
    q = sub.add_parser("agree"); q.add_argument("--a", required=True); q.add_argument("--b-host", required=True)
    q.add_argument("--b-name", required=True); q.add_argument("--template-kwargs", required=True); q.set_defaults(f=cmd_agree)
    sub.add_parser("score").set_defaults(f=cmd_score)
    a = p.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
