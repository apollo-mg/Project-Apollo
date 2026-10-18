#!/usr/bin/env python3
"""Fit a Jacobian lens (anthropics/jacobian-lens 581d398, `jlens`) for Granite 4.1 3B on the RX 9070 XT.

Corpus: WikiText-103 raw, test split (Salesforce/wikitext, test-00000-of-00001.parquet, sha256 5f1bea06..., 732,610 B).
Passages: non-heading paragraphs of at least 100 words, 100 drawn with seed 20261017; jlens truncates to 128 tokens
(its default; the paper used 1,000 x 128 tokens, the README calls ~100 usable). dim_batch 8 (32 runs out of memory);
one passage took 36.5 s in the timing run. bf16 weights; Jacobians accumulate in float32 inside jlens.
Writes passages.json (provenance) here and the lens + resumable checkpoint under /mnt/TG_2TB/models_small/jlens/.
"""
import json, random, time
from pathlib import Path
import pandas as pd, torch, transformers, jlens

HERE = Path(__file__).resolve().parent
CORPUS = "/mnt/TG_2TB/models_small/corpora/wikitext/test-00000-of-00001.parquet"
BASE = "/mnt/TG_2TB/models_small/granite-4.1-3b"
OUT = Path("/mnt/TG_2TB/models_small/jlens"); OUT.mkdir(parents=True, exist_ok=True)
SEED, N = 20261017, 100

lines = pd.read_parquet(CORPUS)["text"].tolist()
elig = [i for i, t in enumerate(lines) if not t.strip().startswith("=") and len(t.split()) >= 100]
pick = sorted(random.Random(SEED).sample(elig, N))
prompts = [lines[i].strip() for i in pick]
json.dump({"corpus": CORPUS, "sha256": "5f1bea067869d04849c0f975a2b29c4ff47d867f484f5010ea5e861eab246d91",
           "seed": SEED, "eligible": len(elig), "line_indices": pick}, open(HERE / "passages.json", "w"), indent=1)
tok = transformers.AutoTokenizer.from_pretrained(BASE)
hf = transformers.AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16).cuda()
model = jlens.from_hf(hf, tok)
t0 = time.time()
lens = jlens.fit(model, prompts=prompts, dim_batch=8, max_seq_len=128, checkpoint_path=str(OUT / "granite41_wikitext100.ckpt.pt"))
lens.save(str(OUT / "granite41_wikitext100.pt"))
print(f"FIT_DONE {N} passages in {time.time() - t0:.0f} s -> {OUT / 'granite41_wikitext100.pt'}", flush=True)
