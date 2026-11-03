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

Recurrence (2026-11-03): all 136 open action threads had mentions == 1, because a thread that comes back in a later
diary comes back REWORDED and failed the 0.7 near-duplicate test. A new item that is not a near-duplicate is matched
against OPEN threads that have no source in the current file, and joins one only on a strong anchor (a file name, a
commit id, a model/quant name, a number with a unit, a backticked identifier) that the two share and at most
ANCHOR_MAX_THREADS open threads carry, PLUS overlap of non-generic words (see recurrence()). Shared generic words alone
("test", "run", "model", "P100") never merge. Closed threads are not candidates: only harvest's own reopen rule (a
near-duplicate in a new file) reopens one. A matched wording is kept in the thread's `variants` (text hashes) so the
next night's re-harvest of the same file finds the same thread without re-matching.

Usage: daydream_harvest.py [--days 3] [--root .] [--dry-run] [--no-recurrence]
  --dry-run also lists every recurrence merge it WOULD make, with the anchor and the shared words, to judge precision.
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


# --- recurrence: a reworded re-mention of an open thread in a later file -------------------------------------------
# Words that recur across unrelated threads by accident: the lab's everyday vocabulary, hardware, and the trigger
# phrases that put an item into the harvest in the first place (every thread has one, so they say nothing).
GENERIC = set("""
test tests tested testing retest re-test re-tested run runs ran running rerun re-run model models p100 p100s gpu gpus
server servers result results receipt receipts check checked need needs needed still yet open next step steps mark
mark's should would could one two three all but has have had after before then when only also more same new now today
tomorrow tonight yesterday again into over under than there their they them what which while about this these those
worth watching pending unresolved verified unverified untested root-caused cause follow-up followup todo question
call go-ahead remains left being measured progress done not never does did doing get got make made use used using
see seen first last time times day days node nodes desktop rx 9070 xt host hosts job jobs file files line lines
diary ledger entry note notes item items thread threads value values number numbers way work works working
""".split())
COMMON_FILES = {"readme.md", "changelog.md", "index.md", "backlog.md", "status.md", "claude.md", "agents.md",
                "gemini.md", "roadmap.md", "failure_modes.md", "profiles.yaml"}
COMMON_ANCHORS = {"q8_0", "f16", "bf16", "f32"}     # the reference quants: named in half the lab's sentences
ANCHOR_MAX_THREADS = 4      # an anchor carried by more open threads than this is not distinctive, so it is not used
FILE_RX = re.compile(r"[\w.-]+\.(?:md|py|sh|json|jsonl|ts|tsx|js|yaml|yml|txt|log|gguf|cpp|cu|c|h|csv)\b", re.I)
COMMIT_RX = re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")
UNIT_RX = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?(gib|gb|mib|mb|kib|kb|tok/s|t/s|ms|min|°c|%|x)(?![\w])", re.I)
TICK_RX = re.compile(r"`([^`\n]{2,80})`")
DATE_RX = re.compile(r"^\d{2,4}(-\d{2}){1,2}$")


def _distinct_number(v):
    """1.9, 0.08, 437 are distinctive; 4, 16, 100, 128 (sizes, round counts) recur by accident."""
    if "." in v:
        return True
    n = int(v)
    return n >= 10 and n % 10 and n & (n - 1)


def anchors(text):
    """{anchor: kind} for the strong, rarely-accidental tokens of an item. Normalised so rewordings agree: file names
    by basename, commit ids by their first 7 hex digits, numbers with units without the space."""
    out = {}
    for f in FILE_RX.findall(text):
        f = f.lower().rsplit("/", 1)[-1].strip(".")
        if f not in COMMON_FILES:
            out[f] = "file"
    for c in COMMIT_RX.findall(text):
        out[c[:7]] = "commit"
    for v, u in UNIT_RX.findall(text):
        if _distinct_number(v):
            out[f"{v}{u.lower()}"] = "number"
    for tok in re.split(r"[\s,;:()\[\]\"'`/]+", text):      # model and quant names: Qwen3.8-27B, Q4_K_M, IQ2_XXS
        tok = tok.strip(".*").lower()
        if (len(tok) >= 4 and re.search(r"[a-z]", tok) and re.search(r"\d", tok) and re.search(r"[-_.]", tok)
                and not FILE_RX.fullmatch(tok) and not UNIT_RX.fullmatch(tok) and not DATE_RX.match(tok)
                and not re.fullmatch(r"\.?\d+(\.\d+)*[a-z]?", tok) and tok not in COMMON_ANCHORS and tok not in GENERIC):
            out.setdefault(tok, "name")
    for t in TICK_RX.findall(text):
        t = t.strip().lower()
        if len(t) >= 4 and t not in GENERIC and t not in STOP and t not in COMMON_ANCHORS \
                and not FILE_RX.fullmatch(t) and t not in COMMON_FILES:
            out.setdefault(t, "ident")
    return out


def content_words(text, anc=()):
    """words() without the generic vocabulary and without the pieces of the item's own anchors (counted once, there)."""
    return {w for w in (x.strip(".") for x in words(text))
            if len(w) >= 3 and w not in GENERIC and w not in STOP and not any(w in a for a in anc)}


def recurrence(state, text, rel, _cache=None):
    """Best OPEN thread that `text` (a new item from file `rel`) is a reworded re-mention of, or None.
    Returns {"thread", "anchors", "words", "ratio", "also"}; `also` counts the other threads that also qualified.

    Rule (precision first): the item and the thread share an anchor that at most ANCHOR_MAX_THREADS open threads carry,
    and their non-generic words overlap: 1 anchor needs >= 3 shared words and overlap >= 0.25 of the smaller set;
    2+ anchors need >= 1 shared word and overlap >= 0.15. Threads with a source in `rel` are not candidates (two items of
    one file are two threads unless they are near-duplicates or adjacent paragraphs, the existing rules)."""
    cache = _cache if _cache is not None else {}
    A = anchors(text)
    if not A:
        return None
    opens = [k for k, t in state["threads"].items() if t.get("status") == "open"]
    for k in opens:
        if k not in cache:
            cache[k] = anchors(state["threads"][k]["text"])
    df = {a: sum(a in cache[k] for k in opens) for a in A}
    strong = {a for a in A if df[a] <= ANCHOR_MAX_THREADS}
    W = content_words(text, A)
    hits = []
    for k in opens:
        t = state["threads"][k]
        shared = strong & set(cache[k])
        if not shared or any(src_file(s) == rel for s in t["sources"]):
            continue
        TW = content_words(t["text"], cache[k])
        sw = W & TW
        ratio = len(sw) / max(1, min(len(W), len(TW)))
        if (len(shared) >= 2 and len(sw) >= 1 and ratio >= 0.15) or (len(sw) >= 3 and ratio >= 0.25):
            hits.append(((len(shared), len(sw), ratio), t["first_seen"], k, shared, sw, ratio))
    if not hits:
        return None
    hits.sort(key=lambda h: (tuple(-x for x in h[0]), h[1]))       # strongest, then the oldest thread
    _, _, k, shared, sw, ratio = hits[0]
    return {"thread": k, "anchors": {a: A[a] for a in sorted(shared)}, "words": sorted(sw), "ratio": round(ratio, 2),
            "also": len(hits) - 1}


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


def ingest(state, root, files, today, use_recurrence=True, log=None):
    """Harvest `files` into `state` (in place). Returns the ids of the threads seen, in order. Recurrence merges are
    appended to `log` (a list) as dicts: source, text, thread, thread_text, anchors, words, ratio, also."""
    normalize(state)
    variants = {v: k for k, t in state["threads"].items() for v in t.get("variants", [])}
    seen_run, cache = [], {}
    for f in files:
        rel = str(Path(f).relative_to(root))
        prev = None                                     # (end line, thread id) of the last paragraph item in this file
        for ln, text, why, end in items(f):
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) < 25:
                continue
            h = hashlib.sha1(text.encode()).hexdigest()[:10]
            match = variants.get(h)                     # a wording already matched by recurrence (re-harvest)
            if match is None:
                match = next((tid for tid, t in state["threads"].items() if similar(t["text"], text) >= 0.7), None)
            if match is None and use_recurrence:
                r = recurrence(state, text, rel, cache)
                if r:
                    match = r["thread"]
                    t = state["threads"][match]
                    t.setdefault("variants", []).append(h)
                    variants[h] = match
                    if log is not None:
                        log.append({"source": f"{rel}:{ln}", "text": text, "thread_text": t["text"], **r})
            if match is None:
                tid = h
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
            files_ = {src_file(s) for s in t["sources"]}
            if t["status"] == "closed" and rel not in files_ and t.get("closed_on", "") < today:
                t["status"] = "open"; t["reopened_on"] = today      # mentioned in a NEW file after closure: reopen
            t["sources"] = [s for s in t["sources"] if src_file(s) != rel] + [src]
            t["mentions"] = len(t["sources"])
            t["last_seen"] = today
            cache.pop(match, None)                      # its text may have grown by a merge
            seen_run.append(match)
    return [survivor(state, k) for k in seen_run]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--dry-run", action="store_true",
                    help="print, do not update the state file; also list the recurrence merges it would make")
    ap.add_argument("--no-recurrence", action="store_true", help="near-duplicate matching only (the pre-11-03 rule)")
    a = ap.parse_args()
    root = Path(a.root)
    outdir = root / "data" / "dev_diaries" / "morning"
    state_p = outdir / "threads_state.json"
    state = json.load(open(state_p)) if state_p.exists() else {"threads": {}}
    today = datetime.date.today().isoformat()
    log = []
    seen_run = ingest(state, root, recent_files(root, a.days), today, not a.no_recurrence, log)
    run = sorted(set(seen_run), key=lambda k: (state["threads"][k]["kind"] != "action", -state["threads"][k]["mentions"],
                                               state["threads"][k]["first_seen"]))
    report = {"date": today, "days": a.days, "n_threads_seen": len(run), "threads": [{"id": k, **state["threads"][k]} for k in run],
              "recurrence": [{k: v for k, v in e.items() if k != "thread_text"} for e in log]}
    if a.dry_run:
        for r in report["threads"]:
            print(f"[{r['kind'][0]}{r['mentions']}] {r['text'][:150]}  <- {r['sources'][0]}")
        print(f"{len(run)} threads")
        print(f"\n{len(log)} recurrence merges (a reworded item joining an open thread from an earlier file):")
        for e in log:
            anc = ", ".join(f"{k} ({v})" for k, v in e["anchors"].items())
            print(f"- {e['source']} -> [{e['thread']}]  anchor: {anc}; shared words: {', '.join(e['words'])} "
                  f"(overlap {e['ratio']}{', also qualified: ' + str(e['also']) if e['also'] else ''})\n"
                  f"    new:    {e['text'][:160]}\n    thread: {e['thread_text'][:160]}")
        return
    outdir.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(state_p, "w"), indent=1, ensure_ascii=False)
    json.dump(report, open(outdir / f"harvest_{today}.json", "w"), indent=1, ensure_ascii=False)
    print(f"{len(run)} threads seen; state has {len(state['threads'])}; {len(log)} recurrence merges")


if __name__ == "__main__":
    main()
