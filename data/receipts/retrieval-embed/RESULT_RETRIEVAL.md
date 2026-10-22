# Result -- the prior-art search's free upgrade is a two-line BM25 fix (recall@6 0.76 -> 0.88 on plain-English queries); EmbeddingGemma 2 adds a little recall and a lot of ranking on top, at 32x the indexing cost

**Prereg:** `PREREG_RETRIEVAL.md` (`6e61c588`, before any arm was scored). **Script:** `eval_retrieval.py`.
**Aggregates:** `RESULT_retrieval.json` (with the registered paired bootstrap, 10,000, seed 20261022), `per_query.json`.

**Run (2026-10-22, desktop CPU, isolated venv `/mnt/TG_2TB/toolchains/embed-venv`: torch 2.14.1+cpu, transformers 5.20.2,
sentence-transformers 6.2.0).** The project venv (sentence-transformers 5.3, transformers 5.10.dev) cannot load
EmbeddingGemma 2 (`embedding_gemma2` needs sentence-transformers >= 6.1), and it also needs Pillow and torchvision even
for text-only use. Corpus 6,818 chunks at run time (6,813 at registration: the hourly ledger indexed 5 chunks in between).
EmbeddingGemma 2 loaded in float32 (the checkpoint defaults to bfloat16, slow on CPU; decided before any scoring).

## Results (368 queries from INDEX.md headlines; gold = the row's receipt; first 6 distinct files)

| arm | short: recall@6 | short: MRR@6 | long: recall@6 | long: MRR@6 |
|---|---:|---:|---:|---:|
| BM25raw (production keyword half) | 0.489 | 0.420 | 0.087 | 0.077 |
| BM25fix (OR of quoted tokens) | 0.875 | 0.688 | 0.894 | 0.769 |
| V-MINI (all-MiniLM-L6-v2) | 0.647 | 0.422 | 0.734 | 0.539 |
| V-EG2 (EmbeddingGemma 2) | 0.766 | 0.577 | 0.815 | 0.680 |
| **H-MINI = production today** | **0.791** | 0.609 | **0.761** | 0.578 |
| H-EG2 | 0.840 | 0.693 | 0.837 | 0.706 |
| H-MINI-fix | 0.851 | 0.640 | 0.883 | 0.713 |
| **H-EG2-fix** | **0.875** | **0.706** | **0.902** | **0.785** |

**The production keyword search fails on most real queries.** Raw text to FTS5 `MATCH` is an implicit AND of every word,
and punctuation is a syntax error that `search_bm25` swallows: on short queries 138 of 368 return nothing and 7 error;
on plain-English queries **287 of 368 are syntax errors** and 28 more return nothing (86 %). Production "hybrid" search
has been mostly vector-only.

## Registered verdicts (paired, 95 % CI)

| # | prediction | outcome |
|---|---|---|
| R1 | V-EG2 beats V-MINI by >= 0.05 recall on long queries | **holds**: +0.082 [+0.038, +0.125] (MRR +0.142) |
| R2 | H-EG2 beats production by >= 0.03 on short queries | **holds**: +0.049 [+0.019, +0.082] |
| R3 | BM25raw fails on >= 25 % of long queries | **holds**: 86 % (287 syntax errors, 28 empty) |
| R4 | the BM25 fix improves the MiniLM hybrid by >= 0.03 on long queries | **holds**: +0.122 [+0.087, +0.160] |

Reported: both upgrades vs production +0.084 [+0.052, +0.120] (short), **+0.141 [+0.103, +0.182]** (long); EG2 on top of
the fix +0.024 [0.000, +0.049] recall but **+0.066 / +0.072 MRR** (it ranks the right receipt higher); BM25fix alone
equals H-EG2-fix on recall (0.000 [-0.019, +0.019] short, -0.008 long).

## Reading

- **Fix the keyword query first.** It is two lines, needs no model, and moves plain-English recall from 0.76 to 0.88.
- **EmbeddingGemma 2 is a real but smaller upgrade on top:** recall +0.02, ranking (MRR) +0.07. Alone it beats MiniLM
  clearly (+0.08 to +0.12 recall). Cost: indexing 6,818 chunks took **42 min on CPU vs 79 s for MiniLM (32x)**; queries
  take ~10-20 ms. And it needs a newer library stack than the project venv.
- **Caveat that favours BM25:** the queries are INDEX headlines, written from the receipts, so they share vocabulary.
  Real questions phrased differently would lean more on the embedding half, where EG2's lead is largest.
