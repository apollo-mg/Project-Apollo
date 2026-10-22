#!/usr/bin/env python3
"""PREREG_RETRIEVAL.md: does EmbeddingGemma 2 (and/or a fixed BM25 query) find the right receipt more often than the
production search (BM25 raw query + all-MiniLM-L6-v2, RRF k=60)?

Corpus: the FTS5 chunks in vault/bm25_index.db, minus INDEX.md and FAILURE_MODES.md (precheck greps those separately,
and the queries are derived from INDEX.md). Queries: each INDEX.md row with a receipt path; gold = any path in the row.
  Q-short: the row's bold headline, numbers and punctuation removed, stopwords removed, first 6 content words
           (the shape of a precheck query).
  Q-long:  the bold headline with numbers removed (a natural-language question).
Ranking is file-level (first chunk per source), top k=6 as `ledger_precheck.py --deep`. Metrics: recall@6, MRR@6.
Embeddings are cached in OUT/emb_*.npy so arms can be re-scored without re-embedding.
"""
import json, re, sqlite3, sys, time
from pathlib import Path
import numpy as np

ROOT = Path("/mnt/TG_2TB/Projects/Apollo"); OUT = ROOT / "data/receipts/retrieval-embed"
EG2 = "/mnt/TG_2TB/models_small/embeddinggemma-2"; MINI = "sentence-transformers/all-MiniLM-L6-v2"
K, RRF_K, POOL = 6, 60, 12            # production: search_bm25(q, 12), search_vector(q, 12), dedupe to k=6 sources
STOP = set("a an the of on in at to for and or but is are was were be been being it its this that these those with "
           "by from as not no than then so if into over under per vs via up down out off only also just more most "
           "less least very same each both all any can does do did has have had will would should could may might "
           "when which what who how why where while after before between about against".split())


def load_corpus():
    con = sqlite3.connect(ROOT / "vault/bm25_index.db")
    rows = con.execute("select chunk_id, source, content from chunks_fts").fetchall(); con.close()
    keep = [r for r in rows if not r[1].endswith(("INDEX.md", "FAILURE_MODES.md"))]
    return keep


def load_queries(sources):
    qs = []
    for line in open(ROOT / "data/receipts/INDEX.md"):
        if not line.startswith("| "): continue
        paths = ["data/receipts/" + p for p in re.findall(r"`([^`]+\.md)`", line)]
        paths = [p for p in paths if p in sources]
        m = re.search(r"\*\*(.+?)\*\*", line)
        if not paths or not m: continue
        head = re.sub(r"`", "", m.group(1))
        long_q = " ".join(re.sub(r"\d+(?:[.,]\d+)*\s*%?", " ", head).split())
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z_]+", head) if w.lower() not in STOP]
        qs.append({"gold": paths, "short": " ".join(words[:6]), "long": long_q})
    return qs


def bm25(con, q, n, mode):
    if mode == "raw": expr = q                                          # production: the query passed through as-is
    else:
        toks = re.findall(r"[A-Za-z0-9_]+", q)
        expr = " OR ".join('"%s"' % t for t in toks) if toks else '""'  # fix: OR of quoted tokens
    try:
        return [r[0] for r in con.execute("select chunk_id from chunks_fts where chunks_fts match ? "
                                          "and source not like '%INDEX.md' and source not like '%FAILURE_MODES.md' "
                                          "order by bm25(chunks_fts) limit ?", (expr, n))], None
    except sqlite3.OperationalError as e:
        return [], str(e)[:60]


def embed(name, texts, is_query, cache):
    if cache.exists(): return np.load(cache)
    from sentence_transformers import SentenceTransformer
    if name == "eg2":
        m = SentenceTransformer(EG2, model_kwargs={}, config_kwargs={"vision_config": None, "audio_config": None})
        texts = [("task: search result | query: " + t) if is_query else t for t in texts]
    else:
        m = SentenceTransformer(MINI)
    t0 = time.time(); v = m.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
    print(f"embedded {len(texts)} with {name} in {time.time() - t0:.1f}s", flush=True)
    np.save(cache, v); return v


def rank_sources(chunk_ids, src_of, k=K):
    out = []
    for c in chunk_ids:
        s = src_of[c]
        if s not in out: out.append(s)
        if len(out) >= k: break
    return out


def rrf(lists):
    sc = {}
    for L in lists:
        for r, c in enumerate(L): sc[c] = sc.get(c, 0) + 1.0 / (RRF_K + r)
    return [c for c, _ in sorted(sc.items(), key=lambda kv: -kv[1])]


def main():
    corpus = load_corpus(); ids = [c[0] for c in corpus]; src_of = {c[0]: c[1] for c in corpus}
    qs = load_queries(set(src_of.values()))
    print(f"corpus {len(corpus)} chunks, {len(set(src_of.values()))} sources; queries {len(qs)}", flush=True)
    docs_eg2 = [f"title: {Path(c[1]).name} | text: {c[2]}" for c in corpus]
    D = {"mini": embed("mini", [c[2] for c in corpus], False, OUT / "emb_docs_mini.npy"),
         "eg2": embed("eg2", docs_eg2, False, OUT / "emb_docs_eg2.npy")}
    con = sqlite3.connect(ROOT / "vault/bm25_index.db")
    res, per = {}, {}
    for form in ("short", "long"):
        texts = [q[form] for q in qs]
        Q = {"mini": embed("mini", texts, True, OUT / f"emb_q_{form}_mini.npy"),
             "eg2": embed("eg2", texts, True, OUT / f"emb_q_{form}_eg2.npy")}
        t0 = time.time()
        for qi, q in enumerate(qs):
            vec = {m: [ids[j] for j in np.argsort(-(D[m] @ Q[m][qi]))[:POOL]] for m in D}
            braw, err = bm25(con, q[form], POOL, "raw"); bfix, _ = bm25(con, q[form], POOL, "fix")
            arms = {"BM25raw": braw, "BM25fix": bfix, "V-MINI": vec["mini"], "V-EG2": vec["eg2"],
                    "H-MINI": rrf([braw, vec["mini"]]), "H-EG2": rrf([braw, vec["eg2"]]),
                    "H-MINI-fix": rrf([bfix, vec["mini"]]), "H-EG2-fix": rrf([bfix, vec["eg2"]])}
            for arm, L in arms.items():
                top = rank_sources(L, src_of); hit = next((i + 1 for i, s in enumerate(top) if s in q["gold"]), None)
                per.setdefault(f"{form}/{arm}", []).append({"hit": hit is not None, "rr": 1.0 / hit if hit else 0.0})
            per.setdefault(f"{form}/bm25raw_status", []).append({"err": err, "n": len(braw)})
        print(f"{form}: scored in {time.time() - t0:.1f}s", flush=True)
    for key, rows in per.items():
        if key.endswith("bm25raw_status"):
            res[key] = {"syntax_error": sum(1 for r in rows if r["err"]), "zero_hits": sum(1 for r in rows if not r["err"] and r["n"] == 0), "n": len(rows)}
        else:
            res[key] = {"recall@6": round(float(np.mean([r["hit"] for r in rows])), 3), "mrr@6": round(float(np.mean([r["rr"] for r in rows])), 3)}
    json.dump({"results": res, "n_queries": len(qs), "corpus_chunks": len(corpus)}, open(OUT / "RESULT_retrieval.json", "w"), indent=1)
    json.dump(per, open(OUT / "per_query.json", "w"))
    for k_, v in res.items(): print(k_, v)


if __name__ == "__main__":
    main()
