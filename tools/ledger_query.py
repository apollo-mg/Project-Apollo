#!/usr/bin/env python3
"""Ask the ledger a question. This is the point of the whole system.

  ./tools/ledger_query.py "what did we conclude about min_p"
  ./tools/ledger_query.py "why did the order test need three runs" -k 5
  ./tools/ledger_query.py "sampling" --all      # search receipts and docs too, not just ledger

Filters to type="ledger" by default so project history is not drowned out by the rest of
shop_vault.

STALE CLAIM CORRECTED 2026-09-20: this docstring used to say "the 238 README / receipt chunks
already in shop_vault". There were ZERO receipt chunks -- the corpus was never indexed. It is
now (5,166 chunks, `tools/receipts_index.py`), so `--all` actually reaches receipts. For
prior-art lookup prefer `tools/ledger_precheck.py --deep`, which fuses BM25 and vectors with RRF
rather than doing vectors alone.
"""
import argparse, sys
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo")
from modules.vdb import get_vector_store

def main(a):
    vs = get_vector_store()
    flt = None if a.all else {"type": "ledger"}
    try:
        res = vs.similarity_search(a.query, k=a.k, filter=flt)
    except Exception as e:
        print(f"query failed: {type(e).__name__}: {e}", file=sys.stderr); return 1
    if not res:
        print("no matches. (ledger may not be indexed yet — run tools/ledger_index.py)")
        return 0
    for i, d in enumerate(res, 1):
        m = d.metadata
        tag = f"{m.get('date','?')} {m.get('time','')}".strip() if m.get("type")=="ledger" \
              else m.get("source", m.get("filename","?"))
        print(f"\n─── [{i}] {tag} ───")
        print(d.page_content[:a.chars].rstrip())
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("query")
    p.add_argument("-k", type=int, default=3)
    p.add_argument("--chars", type=int, default=700)
    p.add_argument("--all", action="store_true", help="search everything, not just the ledger")
    sys.exit(main(p.parse_args()))
