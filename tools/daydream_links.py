#!/usr/bin/env python3
"""Nightly daydream, stage 2: link each open thread to the rest of the corpus, and diff against BACKLOG.md.

Retrieval only; no judgement. Stage 3's model decides what the links mean. For each open ACTION thread in
data/dev_diaries/morning/threads_state.json:
- related: the top hybrid-search hits (BM25 + vectors, RRF; modules/sovereign_search) from other files;
- closure candidates, from five places ("candidate" is the operative word; stage 3's model judges them):
  0. EDITED IN PLACE: the thread's own sentence is no longer in its file; the passage now at its line is shown;
  1. LATER IN THE SAME FILE: a heading or bold lead below the thread's line that shares a term with it and reports an
     outcome. Receipts pose a question under Limits and answer it in an amendment section; diaries note "pending" and
     record the result in a later part of the day. Stage 2 used to skip the thread's own file entirely, and two of the
     first unattended brief's five picks (2026-09-28) were answered a few lines further down;
  2. COMMIT SUBJECTS since the thread's date, by embedding similarity, excluding the commit that wrote the thread's
     own line. A third 09-28 pick (the voice endpointer) was answered only in a commit message (af1a11c);
  3. PREREG -> RESULT: a thread naming PREREG_X.md is answered by RESULT_X*.md in the same directory;
  4. hybrid-search hits from files last committed on or after the thread's own source, whose text carries a
     resolution word (fixed, verified, DONE, superseded, ...). Every retrieved chunk is tested, not a file's first.
For BACKLOG.md:
- every open item (not struck through) gets the same closure-candidate search, limited to recent files;
- every harvested action thread that matches no open BACKLOG item (embedding cosine < --match) is an add candidate.

First refreshes the receipts index for files changed since the last run (tools/receipts_index.py --since), because
the newest receipts are the ones most likely to close a thread.

Usage: daydream_links.py [--days 3] [--match 0.62] [--no-reindex]
"""
import argparse, datetime, functools, json, re, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MORNING = ROOT / "data" / "dev_diaries" / "morning"
RESOLVE = re.compile(r"\b(fixed|fixes|deployed|verified|done|resolved|confirmed|closed|superseded|withdrawn|answered|landed|merged|"
                     r"no longer|now (?:works|survives|restores|has)|re-?scoped|replaced|shelved|parked|dropped|abandoned|"
                     r"deprioriti[sz]ed)\b", re.I)
STOP = set("the a an and or of to in on for is are was were be it this that with as at by from not no its has have but "
           "which when what into than then only also one two per".split())
OUTCOME = re.compile(RESOLVE.pattern[:-3] + r"|result|scored|committed|finished|completed|measured|ran)\b", re.I)
FIXED_ROW = re.compile(r"^\s*(?:\*\*)?(?:fixed|done|closed|resolved|answered|superseded|withdrawn)\b", re.I)
COMMIT_COS = 0.5            # 09-28 calibration: true answers 0.52-0.71, unrelated commits 0.36-0.52; the model judges


@functools.lru_cache(maxsize=None)
def git_date(rel):
    out = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%cs", "--", rel], capture_output=True,
                         text=True).stdout.strip()
    if out:
        return out
    m = re.search(r"(\d{4}-\d{2}-\d{2})", rel)                 # untracked diaries are named by date
    return m.group(1) if m else "0000-00-00"


def fts_query(text):
    ws, seen = [], set()
    for w in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text):
        lw = w.lower()
        if lw not in STOP and lw not in seen:
            seen.add(lw); ws.append(lw)
    return " OR ".join(ws[:14])


def search(text, k=12):
    from modules.sovereign_search import search_bm25, search_vector, rrf_fusion_weighted
    b = search_bm25(fts_query(text), k) if fts_query(text) else []
    v = search_vector(text[:500], k)
    return rrf_fusion_weighted([b, v], k=60)


def snippet(content, n=260):
    m = RESOLVE.search(content)
    if not m:
        return re.sub(r"\s+", " ", content[:n]).strip()
    a = max(0, m.start() - n // 2)
    return ("..." if a else "") + re.sub(r"\s+", " ", content[a:a + n]).strip() + "..."


def terms(text):
    return {w for w in re.findall(r"[a-z][a-z0-9_]{3,}", text.lower()) if w not in STOP}


def later_in_file(src, text, k=2):
    """Closure evidence written further down the thread's own file (see module docstring, source 1)."""
    rel, _, ln = src.rpartition(":")
    try:
        lines = open(ROOT / rel, errors="replace").read().splitlines()
    except OSError:
        return []
    key, hits, in_code, in_details = terms(text), [], False, False
    for n in range(int(ln), len(lines)):                # 0-based n = the line AFTER the thread's 1-based line
        l = lines[n].strip()
        if l.startswith("```"):
            in_code = not in_code; continue
        if "<details" in l:
            in_details = True
        if "</details>" in l:
            in_details = False; continue
        lead = l if l.startswith("#") else (re.match(r"\*\*(.+?)\*\*", l) or [None, ""])[1]
        if in_code or in_details or not lead or not OUTCOME.search(lead):   # a bold lead is matched on the bold part
            continue                                    # only; its paragraph shares words with anything (09-28)
        shared = key & terms(lead)
        if not shared:
            continue
        body = [l]
        for m in range(n + 1, min(n + 8, len(lines))):  # the heading plus the start of what follows it
            if lines[m].strip().startswith("#"):
                break
            body.append(lines[m].strip())
        hits.append((len(shared), -n, {"source": f"{rel}:{n + 1}", "date": git_date(rel), "kind": "later-in-file",
                                       "snippet": re.sub(r"\s+", " ", " ".join(body))[:300]}))
    return [h for _, _, h in sorted(hits, key=lambda x: (-x[0], -x[1]))[:k]]


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[*`_]", "", s)).strip().lower()


def edited_in_place(sources, text):
    """The thread's sentence is gone from EVERY file it was harvested from: the author rewrote it. The rewritten passage
    is the strongest closure evidence there is (09-28: 'is being measured (PREREG_INCTX.md)' had become 'The
    decision-point readout was run (RESULT_INCTX.md)', but the state file kept the old sentence and the brief picked it
    as open). Every source is checked because a thread's other sources may only paraphrase it (similarity match)."""
    probe = norm(text.split(" / ")[0])[:60]
    if len(probe) < 20:
        return []
    for s in sources:
        try:
            if probe in norm((ROOT / s.rpartition(":")[0]).read_text(errors="replace")):
                return []
        except OSError:
            continue
    rel, _, ln = sources[0].rpartition(":")
    try:
        lines = (ROOT / rel).read_text(errors="replace").splitlines()
    except OSError:
        return []
    i = max(0, min(int(ln), len(lines)) - 1)
    a = i
    while a > 0 and lines[a - 1].strip():               # the paragraph that now sits at the thread's line
        a -= 1
    para = []
    for l in lines[a:]:
        if not l.strip():
            break
        para.append(l.strip())
    return [{"source": sources[0], "date": git_date(rel), "kind": "edited-in-place",
             "snippet": "NOW READS: " + re.sub(r"\s+", " ", " ".join(para))[:300]}]


def prereg_results(text, sources):
    """A thread that points at a preregistration ("being measured (`PREREG_INCTX.md`)") is answered by the RESULT file
    that preregistration produced, in the same directory. The lab's result files open with a one-sentence finding, so
    the evidence is that headline plus the result line that best matches the thread (09-28: a pick asked to 'read the
    INCTX result', which had been committed the day before)."""
    out = []
    for name in dict.fromkeys(re.findall(r"PREREG_([A-Za-z0-9_]+)\.md", text)):
        for s in sources:
            d = (ROOT / s.rpartition(":")[0]).parent
            for res in sorted(d.glob(f"RESULT_{name}*.md")):
                lines = res.read_text(errors="replace").splitlines()
                head = next((l.lstrip("# ").strip() for l in lines if l.startswith("#")), "")
                key = terms(text)
                best = max(lines, key=lambda l: len(key & terms(l)), default="")
                rel = str(res.relative_to(ROOT))
                out.append({"source": rel, "date": git_date(rel), "kind": "prereg-result",
                            "snippet": re.sub(r"\s+", " ", f"{head[:180]} ... {best.strip()}")[:400]})
    return out


def own_line_commits(src):
    """Commits that added or removed the thread's own line: the commit that WROTE a question is not its answer."""
    rel, _, ln = src.rpartition(":")
    try:
        raw = open(ROOT / rel, errors="replace").read().splitlines()[int(ln) - 1].strip()
    except (OSError, IndexError, ValueError):
        return set()
    probe = re.sub(r"^[-*+]\s+|^\d+[.)]\s+", "", raw)[:60]
    out = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%h", "-S", probe, "--", rel], capture_output=True,
                         text=True).stdout if len(probe) >= 20 else ""
    made = subprocess.run(["git", "-C", str(ROOT), "log", "--diff-filter=A", "--format=%h", "--", rel],
                          capture_output=True, text=True).stdout       # the commit that created the file wrote the
    return set(out.split()) | set(made.split())                        # question too (f2f67b5, 09-28)


class Commits:
    """Commit subjects since the oldest open thread, embedded once per run (see module docstring, source 2)."""
    def __init__(self, since, until=None):
        rng = [f"--since={since} 00:00"] + ([f"--until={until} 23:59"] if until else [])
        out = subprocess.run(["git", "-C", str(ROOT), "log", *rng, "--format=%h\t%cs\t%s"],
                             capture_output=True, text=True).stdout
        self.rows = [l.split("\t", 2) for l in out.splitlines() if l.count("\t") == 2]
        self.E = embed([r[2][:400] for r in self.rows]) if self.rows else None

    def candidates(self, text, since, exclude, k=2):
        if self.E is None:
            return []
        sc = (embed([text[:500]]) @ self.E.T)[0]
        out = []
        for i in sc.argsort()[::-1]:
            h, d, subj = self.rows[i]
            if sc[i] < COMMIT_COS or len(out) >= k:
                break
            if d >= since and not any(h.startswith(x) or x.startswith(h) for x in exclude):
                out.append({"source": f"commit {h}", "date": d, "kind": "commit", "cos": round(float(sc[i]), 3),
                            "snippet": subj[:300]})
        return out


def links_for(text, own_sources, since, recent_only=None):
    """Every retrieved CHUNK is tested, not just a file's first one: a file's opening chunk is often the original report
    and its resolution is an update section further in (09-28: the INCIDENT file's 'fix landed upstream' update was
    dropped because the file had already been seen via its first chunk, and a fixed bug was picked as open)."""
    own = {s.rpartition(":")[0] for s in own_sources}
    related, closers = {}, {}
    for r in search(text):
        src = r["source"].replace(str(ROOT) + "/", "")
        if src in own or src.endswith(("INDEX.md", "BACKLOG.md")):                  # mirrors, not evidence
            continue
        d = git_date(src)
        if recent_only and d < recent_only:
            continue
        hit = {"source": src, "date": d, "snippet": snippet(r["content"])}
        if d >= since and RESOLVE.search(r["content"]):
            closers.setdefault(src, hit)
            related.pop(src, None)
        elif src not in closers and src not in related and len(related) < 3:
            related[src] = hit
        if len(closers) >= 3 and len(related) >= 3:
            break
    return list(related.values()), list(closers.values())[:3]


def backlog_items():
    """Open BACKLOG.md items: table rows and top-level bullets that are not struck through."""
    out, section = [], None
    for n, l in enumerate(open(ROOT / "data" / "receipts" / "BACKLOG.md").read().splitlines(), 1):
        if l.startswith("## "):
            section = l[3:].strip(); continue
        if section is None:
            continue
        if l.startswith("| ") and not re.match(r"\|\s*(#|---)", l):
            cells = [c.strip() for c in l.strip("|").split("|")]
            if cells and not cells[0].startswith("~~") and len(cells) > 1 and not cells[1].startswith("~~") \
                    and not FIXED_ROW.match(cells[1]):
                out.append({"line": n, "section": section, "id": cells[0], "text": " ".join(cells[1:])[:600]})
        elif l.startswith("- ") and "~~" not in l[:6] and not FIXED_ROW.match(l[2:]):   # "**FIXED in ...**" is closed
            out.append({"line": n, "section": section, "id": f"L{n}", "text": l[2:][:600]})
    return out


def embed(texts):
    from modules.vdb import get_vector_store
    e = np.array(get_vector_store().embeddings.embed_documents(texts))
    return e / np.linalg.norm(e, axis=1, keepdims=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--match", type=float, default=0.62, help="cosine for 'this thread is already in BACKLOG'")
    ap.add_argument("--no-reindex", action="store_true")
    a = ap.parse_args()
    state_p = MORNING / "threads_state.json"
    state = json.load(open(state_p))
    today = datetime.date.today()
    recent = (today - datetime.timedelta(days=a.days - 1)).isoformat()
    if not a.no_reindex:
        ref = state.get("last_indexed_commit") or "HEAD~40"
        r = subprocess.run([str(ROOT / "venv_cachyos/bin/python3"), str(ROOT / "tools/receipts_index.py"), "--since", ref],
                           capture_output=True, text=True, cwd=ROOT)
        state["last_indexed_commit"] = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                                                      text=True).stdout.strip()
        state["last_index_rc"] = r.returncode
        json.dump(state, open(state_p, "w"), indent=1, ensure_ascii=False)
    threads = {k: t for k, t in state["threads"].items() if t["status"] == "open" and t["kind"] == "action"}
    out = {"date": today.isoformat(), "threads": {}, "backlog": {"open_items": 0, "close_candidates": [], "add_candidates": []}}
    sinces = {k: min(git_date(s.rpartition(":")[0]) for s in t["sources"]) for k, t in threads.items()}
    commits = Commits(min(sinces.values())) if threads else None
    for k, t in threads.items():
        since = sinces[k]
        related, closers = links_for(t["text"], t["sources"], since)
        later = [h for s in t["sources"] for h in later_in_file(s, t["text"])]
        own = set().union(*(own_line_commits(s) for s in t["sources"]))
        edited = edited_in_place(t["sources"], t["text"])
        cands = edited + prereg_results(t["text"], t["sources"]) + later + commits.candidates(t["text"], since, own) + closers
        seen, uniq = set(), []
        for c in cands:
            if c["source"] not in seen:
                seen.add(c["source"]); uniq.append(c)
        out["threads"][k] = {"text": t["text"], "sources": t["sources"], "since": since, "related": related,
                             "closure_candidates": uniq[:5]}
    items = backlog_items()
    out["backlog"]["open_items"] = len(items)
    for it in items:
        _, closers = links_for(it["text"], ["data/receipts/BACKLOG.md"], recent, recent_only=recent)
        if closers:
            out["backlog"]["close_candidates"].append({**it, "evidence": closers})
    if items and threads:
        tk = list(threads)
        T = embed([threads[k]["text"] for k in tk]); B = embed([i["text"] for i in items])
        S = T @ B.T
        for n, k in enumerate(tk):
            j = int(S[n].argmax())
            out["threads"][k]["backlog_match"] = {"item": items[j]["id"], "line": items[j]["line"], "cos": round(float(S[n, j]), 3)}
            if S[n, j] < a.match:
                out["backlog"]["add_candidates"].append({"thread": k, "text": threads[k]["text"], "sources": threads[k]["sources"],
                                                         "nearest": items[j]["id"], "cos": round(float(S[n, j]), 3)})
    json.dump(out, open(MORNING / f"links_{today.isoformat()}.json", "w"), indent=1, ensure_ascii=False)
    nc = sum(bool(v["closure_candidates"]) for v in out["threads"].values())
    print(f"{len(threads)} open action threads: {nc} with closure candidates | BACKLOG: {len(items)} open items, "
          f"{len(out['backlog']['close_candidates'])} close candidates, {len(out['backlog']['add_candidates'])} add candidates")


if __name__ == "__main__":
    main()
