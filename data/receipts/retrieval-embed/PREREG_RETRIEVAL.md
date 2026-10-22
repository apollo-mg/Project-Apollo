# PREREG -- A free upgrade for the prior-art search? EmbeddingGemma 2 vs all-MiniLM-L6-v2, and a fixed BM25 query

**Registered 2026-10-22, before any arm is scored.** Script: `eval_retrieval.py` (committed with this file).

**Prior art checked:** `ledger_precheck.py "embedding model retrieval MiniLM semantic search receipts"` -> incidental
matches only (INDEX L499: precheck does not search upstream issue trackers); nothing has measured the search itself.

## Why

`ledger_precheck.py --deep` is the control that stops re-derived experiments. It fuses BM25 (SQLite FTS5) with
all-MiniLM-L6-v2 vectors by RRF (`modules/sovereign_search.py`). Two things found while designing this:
- **The BM25 half passes the query raw to FTS5 `MATCH`.** A multi-word query is an implicit AND of every word, and any
  `.`/`-`/`:` is a syntax error that `search_bm25` swallows (`Qwen3.8 decode` -> `fts5: syntax error near "."`). For
  many queries the "hybrid" search is vector-only.
- **MiniLM (2021, 22M) is the vector half.** `google/embeddinggemma-2` (2026-09, Apache-2.0, 270M text backbone,
  768-d, 8K context, task prefixes) is the candidate. Download 1.49 GB, sha256 `197a32965d4b1105...` verified.

## Instrument

- **Corpus:** the 6,813 FTS5 chunks in `vault/bm25_index.db` excluding `INDEX.md` and `FAILURE_MODES.md` (precheck greps
  those itself, and the queries come from INDEX.md). Both embedding models embed the same chunks (normalized, cosine).
  EmbeddingGemma 2 documents as `title: <filename> | text: <chunk>`, queries as `task: search result | query: <q>`.
- **Queries (mechanical):** every INDEX.md row with a receipt path present in the corpus and a bold headline: **368**.
  Gold = any receipt path in the row. Q-short = first 6 non-stopword words of the headline (a precheck-style query);
  Q-long = the headline with numbers removed.
- **Ranking as production:** 12 candidates per list, RRF k=60, deduplicated to the first **6 sources** (precheck `-k 6`).
  Metrics: recall@6 (gold source among the 6), MRR@6.
- **Arms:** BM25raw, BM25fix (OR of quoted tokens), V-MINI, V-EG2, H-MINI (= production), H-EG2, H-MINI-fix, H-EG2-fix.
- Paired comparisons by McNemar-style bootstrap over queries (10,000, seed 20261022).

## Predictions

| # | prediction |
|---|---|
| R1 | V-EG2 beats V-MINI on recall@6 by >= 0.05 on Q-long (embedding quality) |
| R2 | H-EG2 beats H-MINI (production) on recall@6 by >= 0.03 on Q-short (the swap is worth doing) |
| R3 | BM25raw fails (syntax error or zero hits) on >= 25 % of Q-long queries |
| R4 | the fixed BM25 query improves the MiniLM hybrid: H-MINI-fix - H-MINI >= +0.03 on Q-long |

## Known limits, stated now

- Queries come from INDEX headlines, which were written from the receipts: phrasing overlaps, which favours BM25.
- One corpus, one author's vocabulary; recall@6 at file level only.
