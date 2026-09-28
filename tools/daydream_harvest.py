#!/usr/bin/env python3
"""Nightly daydream, stage 1: harvest open threads MECHANICALLY from recent ledger diaries and receipts.

No model. Following LEDGER_SPEC's principle: extract the skeleton mechanically; a model only writes reasoning
around a structure it did not have to find. Stage 2 (closure check against chroma) and stage 3 (the model pass and
the morning brief) consume this file's output.

Where loose threads live, by this repo's own conventions:
- sections: "Not established", "Open items", "Open questions", "Limits", "Known gaps", "Not fixed", "Remaining",
  "Pending", "Next steps" -> every bullet under them;
- anywhere: bullets or sentences carrying a trigger phrase ("not yet", "not re-tested", "not root-caused", "not run",
  "untested", "worth watching", "needs Mark", "go-ahead", "unresolved", ...).
Skipped: the ledger's <details> skeleton blocks (raw commands and quoted human turns) and fenced code.

State (data/dev_diaries/morning/threads_state.json): one record per thread, merged across days by token overlap,
with first_seen / last_seen / mentions / sources. Nothing is ever closed here; closure is stage 2's job.

Usage: daydream_harvest.py [--days 3] [--root .] [--dry-run]
"""
import argparse, datetime, hashlib, json, os, re, subprocess
from pathlib import Path

SECTION = re.compile(r"not established|open items?|open questions?|\blimits\b|known gaps?|not fixed|remaining|"
                     r"pending|next steps?|still open|unresolved", re.I)
TRIGGER = re.compile(r"not yet|not re-?tested|untested|not tested|not root-caused|root cause (?:is )?(?:unknown|open)|"
                     r"not run\b|was not run|not reproduced|never reproduced|worth watching|needs? mark|mark's call|"
                     r"go-ahead|unresolved|remains? open|left open|is open\b|re-scoped|pending|still unknown|"
                     r"not verified|unverified|todo\b|follow-?up|open question|being measured|in progress when", re.I)
HEADING = re.compile(r"^(#{1,6})\s+(.*)$|^\*\*([^*]{3,80}?)[:.]?\*\*\s*:?\s*$")
BULLET = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$")
# "action": something to do or decide; "scope": a stated limit of a finished result (one model, thinking off, n = 3).
# Most "Not established" bullets are scope. The brief leads with action and keeps scope as context only.
ACTION = re.compile(r"next (test|step)|should|needs?\b|must\b|not re-?tested|not (yet )?run|pending|mark's call|go-ahead|"
                    r"worth watching|root-caus|unchanged|unfixed|not fixed|open question|is open\b|being measured|re-scoped|"
                    r"todo\b|follow-?up|untested|not tested|unverified|not verified|not reproduced|in progress when|"
                    r"would need|requires?\b|blocked|workaround", re.I)
STOP = set("the a an and or of to in on for is are was were be it this that with as at by from not no".split())


def words(t):
    return {w for w in re.findall(r"[a-z0-9_.]{3,}", t.lower()) if w not in STOP}


def similar(a, b):
    A, B = words(a), words(b)
    return len(A & B) / max(1, min(len(A), len(B))) if A and B else 0.0


def recent_files(root, days):
    since = (datetime.date.today() - datetime.timedelta(days=days - 1))
    diaries = sorted(p for p in (root / "data" / "dev_diaries").glob("*_ledger.md")
                     if p.name[:10] >= since.isoformat())
    out = subprocess.run(["git", "-C", str(root), "log", f"--since={since.isoformat()} 00:00", "--name-only",
                          "--pretty=format:", "--", "data/receipts"], capture_output=True, text=True).stdout
    # INDEX.md / BACKLOG.md / FAILURE_MODES.md mirror other receipts; BACKLOG is diffed separately (stage 2), and
    # harvesting its own lines re-surfaced stale entries as fresh threads (first brief, 2026-09-27).
    receipts = sorted({root / l for l in out.splitlines() if l.endswith(".md") and (root / l).exists()
                       and not l.endswith(("INDEX.md", "BACKLOG.md", "FAILURE_MODES.md"))})
    return diaries + receipts


def items(path):
    """Yield (line_no, text, why, end) for every candidate thread in one markdown file. `end` is the last line of a
    paragraph, None for a bullet (bullets are separate items by construction; adjacent paragraphs may be one thread).
    Preregistrations are procedure ("if X, that is a Deviation"), so only their sections are harvested, never their
    trigger sentences."""
    prereg = Path(path).name.startswith("PREREG_")
    lines = open(path, errors="replace").read().splitlines()
    in_details = in_code = False
    sec, sec_level = None, 99
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.strip().startswith("```"):
            in_code = not in_code; i += 1; continue
        if "<details" in l:
            in_details = True
        if "</details>" in l:
            in_details = False; i += 1; continue
        if in_code or in_details:
            i += 1; continue
        h = HEADING.match(l.strip())
        if h:
            level = len(h.group(1)) if h.group(1) else 7        # bold pseudo-heading: below every real one
            title = h.group(2) or h.group(3) or ""
            if SECTION.search(title):
                sec, sec_level = title.strip(), level
            elif level <= sec_level:
                sec, sec_level = None, 99
            i += 1; continue
        b = BULLET.match(l)
        if b:
            indent, text = len(b.group(1)), b.group(2)
            j = i + 1                                       # continuation lines of this bullet
            while j < len(lines) and lines[j].strip() and not BULLET.match(lines[j]) and not HEADING.match(lines[j].strip()) \
                    and (len(lines[j]) - len(lines[j].lstrip())) > indent:
                text += " " + lines[j].strip(); j += 1
            if sec:
                yield i + 1, text, f"section: {sec}", None
            elif TRIGGER.search(text) and not prereg:
                yield i + 1, text, f"trigger: {TRIGGER.search(text).group(0)}", None
            i = j; continue
        if l.strip() and not l.lstrip().startswith(("|", "<", ">")):
            j, para = i, []                                 # a whole paragraph: receipts hard-wrap at 120
            while j < len(lines) and lines[j].strip() and not BULLET.match(lines[j]) \
                    and not HEADING.match(lines[j].strip()) and not lines[j].strip().startswith(("```", "|", "<")):
                para.append(lines[j].strip()); j += 1
            text, end = " ".join(para), j
            if sec:
                yield i + 1, text, f"section: {sec}", end
            elif TRIGGER.search(text) and not prereg:
                if len(text) <= 400:
                    yield i + 1, text, f"trigger: {TRIGGER.search(text).group(0)}", end
                else:                                       # long paragraph: the triggered sentence + the one before
                    sents = re.split(r"(?<=[.!?])\s+", text)
                    for k, snt in enumerate(sents):
                        if TRIGGER.search(snt):
                            yield i + 1, " ".join(sents[max(0, k - 1):k + 1]), f"trigger: {TRIGGER.search(snt).group(0)}", end
            i = max(j, i + 1); continue
        i += 1


def src_file(s):
    return s.rpartition(":")[0]


def normalize(state):
    """One source per FILE, at its newest line: when a receipt is edited its lines shift, and the same sentence at a
    new line number is not a new mention (09-28: RESULT_CALIB.md:189 and :192 counted as two). mentions = distinct
    files. Applied on every load, so older state files are migrated in place."""
    for t in state["threads"].values():
        by_file = {}
        for s in t["sources"]:
            by_file[src_file(s)] = s
        t["sources"] = list(by_file.values())
        t["mentions"] = len(t["sources"])


def survivor(state, tid):
    while state["threads"][tid].get("status") == "merged":
        tid = state["threads"][tid]["merged_into"]
    return tid


def merge(state, keep, drop):
    """Fold thread `drop` into `keep`: adjacent paragraphs of one passage are one thread (09-28: a single 'stage 2
    re-scoped' passage was harvested as three threads and filled the BACKLOG add list)."""
    K, D = state["threads"][keep], state["threads"][drop]
    if D["text"] not in K["text"]:
        K["text"] = (K["text"] + " / " + D["text"])[:900]
    have = {src_file(s) for s in K["sources"]}
    K["sources"] += [s for s in D["sources"] if src_file(s) not in have]
    K["mentions"] = len(K["sources"])
    K["first_seen"] = min(K["first_seen"], D["first_seen"])
    if D["kind"] == "action":
        K["kind"] = "action"
    D.update(status="merged", merged_into=keep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--dry-run", action="store_true", help="print, do not update the state file")
    a = ap.parse_args()
    root = Path(a.root)
    outdir = root / "data" / "dev_diaries" / "morning"
    state_p = outdir / "threads_state.json"
    state = json.load(open(state_p)) if state_p.exists() else {"threads": {}}
    normalize(state)
    today = datetime.date.today().isoformat()
    seen_run = []
    for f in recent_files(root, a.days):
        rel = str(f.relative_to(root))
        prev = None                                     # (end line, thread id) of the last paragraph item in this file
        for ln, text, why, end in items(f):
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) < 25:
                continue
            match = next((tid for tid, t in state["threads"].items() if similar(t["text"], text) >= 0.7), None)
            if match is None:
                tid = hashlib.sha1(text.encode()).hexdigest()[:10]
                state["threads"][tid] = {"text": text, "first_seen": today, "last_seen": today, "mentions": 0,
                                         "sources": [], "why": why, "status": "open",
                                         "kind": "action" if ACTION.search(text) else "scope"}
                match = tid
            match = survivor(state, match)              # a fragment folded into another thread counts for that thread
            if end is not None and prev and ln - prev[0] <= 2 and survivor(state, prev[1]) != match:
                keep = survivor(state, prev[1])         # same paragraph, or the next one after a blank line
                merge(state, keep, match)
                match = keep
            prev = (end, match) if end is not None else None
            t = state["threads"][match]
            src = f"{rel}:{ln}"
            files = {src_file(s) for s in t["sources"]}
            if t["status"] == "closed" and rel not in files and t.get("closed_on", "") < today:
                t["status"] = "open"; t["reopened_on"] = today      # mentioned in a NEW file after closure: reopen
            t["sources"] = [s for s in t["sources"] if src_file(s) != rel] + [src]
            t["mentions"] = len(t["sources"])
            t["last_seen"] = today
            seen_run.append(match)
    seen_run = [survivor(state, k) for k in seen_run]
    run = sorted(set(seen_run), key=lambda k: (state["threads"][k]["kind"] != "action", -state["threads"][k]["mentions"],
                                               state["threads"][k]["first_seen"]))
    report = {"date": today, "days": a.days, "n_threads_seen": len(run), "threads": [{"id": k, **state["threads"][k]} for k in run]}
    if a.dry_run:
        for r in report["threads"]:
            print(f"[{r['kind'][0]}{r['mentions']}] {r['text'][:150]}  <- {r['sources'][0]}")
        print(f"{len(run)} threads")
        return
    outdir.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(state_p, "w"), indent=1, ensure_ascii=False)
    json.dump(report, open(outdir / f"harvest_{today}.json", "w"), indent=1, ensure_ascii=False)
    print(f"{len(run)} threads seen; state has {len(state['threads'])}")


if __name__ == "__main__":
    main()
