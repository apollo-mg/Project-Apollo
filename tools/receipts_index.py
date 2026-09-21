#!/usr/bin/env python3
"""Index data/receipts into BOTH retrieval stores, so the corpus is actually searchable.

    ./tools/receipts_index.py              # index everything
    ./tools/receipts_index.py --dry-run    # count chunks, embed nothing
    ./tools/receipts_index.py --pattern 'data/receipts/exl3-campaign/*.md'

WHY THIS EXISTS
---------------
Measured 2026-09-20, before this ran:

    Chroma shop_vault : 345 docs  (skill 145, ledger 107, text 81)  -- 0 from receipts
    SQLite FTS5       :  92 rows  (todo.md, CHANGELOG.md, README)   -- 0 from receipts

588 receipts, the most valuable thing in the repo, in neither store. `ledger_query.py`'s
docstring claims "238 README / receipt chunks already in shop_vault"; that is stale, it is zero.

This is the mechanical reason re-derivation keeps happening. INDEX.md is a hand-maintained
mechanism index that goes stale (170 unindexed receipts on the same day), and semantic search
cannot find what was never embedded, so BOTH lookup paths were failing at once. On 2026-09-20 a
session re-derived a July finding while the answer sat in a receipt no index could reach.

BOTH STORES, deliberately. modules/sovereign_search.py already implements hybrid retrieval --
BM25 via FTS5, vectors via Chroma, fused with RRF (k=60). Hybrid matters more than usual here:
receipt language is full of exact tokens a vector model blurs (`__dp4a`, `sm_60`, `cache_prompt`,
`kv_bpv`, `O8`, `AFM-26`). BM25 nails those; embeddings catch "why was the quantizer slow".
Indexing to only one store would waste a working fusion layer.

Idempotent: chunk ids are deterministic (`receipt:<relpath>#<n>`), Chroma upserts on explicit id,
and FTS5 rows for a file are deleted before reinsert.
"""
import argparse, sqlite3, sys, os
from pathlib import Path

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
sys.path.insert(0, str(ROOT))
FTS = ROOT / "vault/bm25_index.db"
RECEIPTS = ROOT / "data/receipts"

# Raw dumps, logs and captured state are not prose. Embedding them buries the findings they
# support -- the same reason ledger_index.py strips <details> skeleton blocks.
SKIP_DIRS = {"raw", "logs", "state", "runs", "sandbox"}

def files(pattern):
    if pattern:
        import glob
        # resolve(): a relative glob yields relative paths, and relative_to(ROOT) below
        # then raises. --pattern was unusable from the repo root because of it.
        return [Path(p).resolve() for p in sorted(glob.glob(pattern))
                if Path(p).resolve().is_file()]
    out = []
    for p in sorted(RECEIPTS.rglob("*.md")):
        if set(p.relative_to(RECEIPTS).parts[:-1]) & SKIP_DIRS:
            continue
        out.append(p)
    return out

def changed_since(ref):
    """Receipt .md files touched since `ref`, as absolute paths that still exist."""
    import subprocess
    r = subprocess.run(["git", "-C", str(ROOT), "diff", "--name-only", "--diff-filter=d",
                        ref, "--", "data/receipts"], capture_output=True, text=True)
    if r.returncode != 0:
        return None                      # bad ref: caller decides, never silently index all
    out = []
    for line in r.stdout.splitlines():
        p = (ROOT / line).resolve()
        if p.suffix == ".md" and p.is_file() and not (
                set(p.relative_to(RECEIPTS).parts[:-1]) & SKIP_DIRS):
            out.append(p)
    return out


def main(a):
    from modules.vdb import get_vector_store, get_text_splitter
    from langchain_core.documents import Document

    splitter = get_text_splitter()
    if a.since:
        paths = changed_since(a.since)
        if paths is None:
            print(f"receipts_index: bad git ref {a.since!r}; refusing to index everything")
            return 1
        if not paths:
            print(f"receipts_index: no receipts changed since {a.since}; nothing to do")
            return 0
        print(f"receipts_index: {len(paths)} receipt(s) changed since {a.since}")
    else:
        paths = files(a.pattern)
    docs, ids, per_file = [], [], {}
    for p in paths:
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        if len(text.strip()) < 200:      # stubs and pointers carry no retrievable claim
            continue
        rel = str(p.relative_to(ROOT))
        parts = p.relative_to(RECEIPTS).parts
        campaign = parts[0] if len(parts) > 1 else "(root)"
        chunks = splitter.split_text(text)
        per_file[rel] = []
        for i, ch in enumerate(chunks):
            cid = f"receipt:{rel}#{i}"
            ids.append(cid)
            per_file[rel].append((cid, ch))
            docs.append(Document(page_content=ch, metadata={
                "type": "receipt", "source": rel, "campaign": campaign,
                "name": p.name, "chunk": i}))

    print(f"{len(paths)} files -> {len(docs)} chunks across {len(per_file)} indexable receipts")
    if a.dry_run:
        from collections import Counter
        c = Counter(d.metadata["campaign"] for d in docs)
        for k, v in c.most_common(10):
            print(f"   {v:5d}  {k}")
        return 0
    if not docs:
        print("nothing to index"); return 0

    # --- FTS5 (BM25 half of the hybrid) ---
    if FTS.exists():
        conn = sqlite3.connect(FTS)
        n = 0
        try:
            for rel, chunks in per_file.items():
                conn.execute("DELETE FROM chunks_fts WHERE source = ?", (rel,))
                conn.executemany(
                    "INSERT INTO chunks_fts(chunk_id, source, content) VALUES (?,?,?)",
                    [(cid, rel, ch) for cid, ch in chunks])
                n += len(chunks)
            conn.commit()
            print(f"FTS5: {n} rows (total now {conn.execute('SELECT count(*) FROM chunks_fts').fetchone()[0]})")
        finally:
            conn.close()
    else:
        print(f"FTS5 skipped: {FTS} missing")

    # --- Chroma (vector half) ---
    vs = get_vector_store()
    B = 256
    for i in range(0, len(docs), B):
        vs.add_documents(docs[i:i+B], ids=ids[i:i+B])
        print(f"  chroma {min(i+B, len(docs))}/{len(docs)}", flush=True)
    print(f"chroma: collection now {vs._collection.count()} docs")
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pattern", default=None)
    p.add_argument("--since", default=None,
                   help="index only receipts changed since this git ref (e.g. HEAD~1). "
                        "Exits 0 with no work when nothing under data/receipts changed, so it "
                        "is cheap to call from a hook on every commit.")
    p.add_argument("--dry-run", action="store_true")
    sys.exit(main(p.parse_args()))
