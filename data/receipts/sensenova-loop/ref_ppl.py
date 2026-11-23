#!/usr/bin/env python3
"""PREREG_SENSENOVA_LOOP Amendment 1: the reference implementation's wikitext perplexity, scored as llama-perplexity
scores it (examples/perplexity: the whole file tokenized once with no BOS -- the model adds none; chunks of n_ctx
tokens; logits rows n_ctx/2 .. n_ctx-2 predict tokens n_ctx/2+1 .. n_ctx-1, i.e. 255 scored tokens per 512-token
chunk; the running estimate is exp(total NLL / total scored)). FP32 on CPU, SenseTime's modeling code
(trust_remote_code, read in full before this runs), use_cache off.
Usage: ref_ppl.py MODEL_DIR WIKI_FILE OUT_JSON [CHUNKS=20] [THREADS]"""
import json, math, os, sys, time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL, WIKI, OUT = sys.argv[1:4]
NCH = int(sys.argv[4]) if len(sys.argv) > 4 else 20
if len(sys.argv) > 5: torch.set_num_threads(int(sys.argv[5]))
NCTX, FIRST = 512, 256

tok = AutoTokenizer.from_pretrained(MODEL)
ids = tok(open(WIKI, encoding="utf-8").read(), add_special_tokens=False)["input_ids"]
print(f"tokens {len(ids)}; chunks available {len(ids) // NCTX}; scoring {NCH}; threads {torch.get_num_threads()}", flush=True)
t0 = time.time()
model = AutoModelForCausalLM.from_pretrained(MODEL, trust_remote_code=True, dtype=torch.float32)
model.eval()
plan = getattr(getattr(model, "model", model), "language_model", None)
print(f"loaded in {time.time() - t0:.0f} s; class {type(model).__name__}; "
      f"loop plan {getattr(plan, '_loop_plan', 'not found')}", flush=True)

nll, cnt, rows = 0.0, 0, []
for c in range(NCH):
    x = torch.tensor([ids[c * NCTX:(c + 1) * NCTX]])
    t1 = time.time()
    with torch.no_grad():
        logits = model(input_ids=x, use_cache=False).logits[0].float()
    lp = torch.log_softmax(logits[FIRST:NCTX - 1], dim=-1)
    tgt = x[0, FIRST + 1:NCTX]
    s = -lp.gather(1, tgt[:, None]).sum().item()
    nll += s; cnt += len(tgt)
    rows.append({"chunk": c + 1, "chunk_ppl": math.exp(s / len(tgt)), "running_ppl": math.exp(nll / cnt),
                 "seconds": round(time.time() - t1, 1)})
    print(json.dumps(rows[-1]), flush=True)
    json.dump({"model_dir": os.path.basename(MODEL.rstrip("/")), "n_ctx": NCTX, "scored_per_chunk": NCTX - 1 - FIRST,
               "chunks": rows, "final_ppl": math.exp(nll / cnt), "torch": torch.__version__,
               "transformers": __import__("transformers").__version__}, open(OUT, "w"), indent=1)
print(f"Final estimate: PPL = {math.exp(nll / cnt):.4f} over {NCH} chunks", flush=True)
