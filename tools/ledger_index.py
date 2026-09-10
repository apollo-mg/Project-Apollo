#!/usr/bin/env python3
"""Index ledger entries into Apollo's EXISTING vector store, so the diary is retrievable.

WHY NOT A HAND-MAINTAINED INDEX: dated files with no search is exactly what killed the first
dev_diaries attempt -- a diary you cannot search is one you stop reading, and one you stop
reading is one nobody notices has broken. Apollo already has semantic retrieval
(vault/chroma_db, all-MiniLM-L6-v2, local embeddings, no API), populated and working. Building
a third retrieval mechanism next to it would repeat the mistake INDEX.md exists to prevent.

Entries are tagged type="ledger" so they coexist with the existing type="text"/"memory_flush"
docs and can be filtered out of, or into, any query.

Idempotent: each run section gets a deterministic id (file + timestamp heading), so re-indexing
a day updates rather than duplicates.
"""
import argparse, glob, os, re, sys
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo")
from modules.vdb import get_vector_store
from langchain_core.documents import Document

SEC = re.compile(r"^## (\d{2}:\d{2}) — (\d+) events\s*$", re.M)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger_validate import classify

def sections(path):
    """Split a day file into per-run sections. Skeleton blocks are stripped -- they are raw
    telemetry, and embedding them would swamp the prose they exist to support."""
    text = open(path, errors="replace").read()
    marks = [(m.start(), m.group(1), m.group(2)) for m in SEC.finditer(text)]
    for i, (pos, stamp, n) in enumerate(marks):
        end = marks[i+1][0] if i+1 < len(marks) else len(text)
        body = text[pos:end]
        body = re.sub(r"<details>.*?</details>", "", body, flags=re.S).strip()
        if len(body) > 120:
            yield stamp, int(n), body

def main(a):
    vs = get_vector_store()
    files = sorted(glob.glob(a.pattern))
    docs, ids, skipped, stale_ids = [], [], [], []
    for f in files:
        day = os.path.basename(f).split("_")[0]
        for stamp, n, body in sections(f):
            # Do not index a section that is not an entry. Six of the first eighteen sections
            # were degenerate `////` runs and two were raw chain-of-thought; indexing those makes
            # retrieval return garbage, which is worse than having no entry for that slot. The
            # file keeps them as history -- the vector store should not.
            bad = classify(body)
            if bad:
                skipped.append((os.path.basename(f), stamp, bad))
                # Skipping is not enough on a re-index: ids are upserted, so a section indexed
                # while it was still considered good stays in the collection forever unless it is
                # explicitly removed. Delete, then skip.
                stale_ids.append(f"ledger:{day}:{stamp}")
                continue
            ids.append(f"ledger:{day}:{stamp}")
            docs.append(Document(page_content=body,
                metadata={"type": "ledger", "date": day, "time": stamp,
                          "events": n, "source": os.path.basename(f)}))
    if stale_ids:
        try:
            vs.delete(ids=stale_ids)
            print(f"purged {len(stale_ids)} malformed section(s) from the collection")
        except Exception as e:
            print(f"purge failed ({type(e).__name__}: {e}) — malformed sections may still be searchable")
    if not docs:
        print("no ledger sections found"); return 0
    vs.add_documents(docs, ids=ids)          # explicit ids => upsert, not duplicate
    for fn, stamp, why in skipped:
        print(f"  SKIPPED {fn} {stamp}: {why}")
    print(f"indexed {len(docs)} ledger sections from {len(files)} file(s)"
          + (f", skipped {len(skipped)} malformed" if skipped else ""))
    print(f"collection now: {vs._collection.count()} docs")
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pattern", default="/mnt/TG_2TB/Projects/Apollo/data/dev_diaries/*_ledger.md")
    sys.exit(main(p.parse_args()))
