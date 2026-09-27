#!/usr/bin/env python3
"""Nightly daydream, stage 2: link each open thread to the rest of the corpus, and diff against BACKLOG.md.

Retrieval only; no judgement. Stage 3's model decides what the links mean. For each open ACTION thread in
data/dev_diaries/morning/threads_state.json:
- related: the top hybrid-search hits (BM25 + vectors, RRF; modules/sovereign_search) from other files;
- closure candidates: hits from files last committed on or after the thread's own source, whose text carries a
  resolution word (fixed, verified, DONE, superseded, ...). "Candidate" is the operative word.
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
RESOLVE = re.compile(r"\b(fixed|verified|done|resolved|confirmed|closed|superseded|withdrawn|answered|landed|merged|"
                     r"no longer|now (?:works|survives|restores|has)|re-?scoped|replaced|shelved|parked|dropped|abandoned|"
                     r"deprioriti[sz]ed)\b", re.I)
STOP = set("the a an and or of to in on for is are was were be it this that with as at by from not no its has have but "
           "which when what into than then only also one two per".split())


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


def links_for(text, own_sources, since, recent_only=None):
    own = {s.split(":")[0] for s in own_sources}
    related, closers, seen = [], [], set()
    for r in search(text):
        src = r["source"].replace(str(ROOT) + "/", "")
        if src in own or src in seen or src.endswith(("INDEX.md", "BACKLOG.md")):   # mirrors, not evidence
            continue
        seen.add(src)
        d = git_date(src)
        if recent_only and d < recent_only:
            continue
        hit = {"source": src, "date": d, "snippet": snippet(r["content"])}
        if d >= since and RESOLVE.search(r["content"]):
            closers.append(hit)
        elif len(related) < 3:
            related.append(hit)
        if len(closers) >= 3 and len(related) >= 3:
            break
    return related, closers[:3]


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
            if cells and not cells[0].startswith("~~") and len(cells) > 1 and not cells[1].startswith("~~"):
                out.append({"line": n, "section": section, "id": cells[0], "text": " ".join(cells[1:])[:600]})
        elif l.startswith("- ") and "~~" not in l[:6]:
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
    for k, t in threads.items():
        since = min(git_date(s.split(":")[0]) for s in t["sources"])
        related, closers = links_for(t["text"], t["sources"], since)
        out["threads"][k] = {"text": t["text"], "sources": t["sources"], "since": since, "related": related,
                             "closure_candidates": closers}
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
