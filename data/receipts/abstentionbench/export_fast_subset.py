#!/usr/bin/env python3
"""Export AbstentionBench's fast subset to one JSONL, using Meta's own dataset classes and configs exactly as main.py does:
every configs/dataset/*.yaml except dummy (and FreshQA: needs a manual Google Sheets export), instantiated via hydra;
indices from data/fast-subset-indices.json keyed by the config's dataset_name, or the full dataset when absent.
Run from the AbstentionBench checkout with its venv:  python export_fast_subset.py OUT.jsonl"""
import glob, json, os, sys, time, traceback
sys.path.insert(0, os.getcwd())   # the AbstentionBench checkout, so hydra can import recipe.abstention_datasets
from hydra.utils import instantiate
from omegaconf import OmegaConf
OUT = sys.argv[1]
fast = json.load(open("data/fast-subset-indices.json"))
done = set()
if os.path.exists(OUT):
    for l in open(OUT): done.add(json.loads(l)["dataset"])
log = open(OUT + ".log", "a")
def say(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); log.write(s + "\n"); log.flush()
for cfg_path in sorted(glob.glob("configs/dataset/*.yaml")):
    stem = os.path.basename(cfg_path)[:-5]
    if stem in ("dummy", "freshqa"): continue
    # main.py merges configs/default_pipeline.yaml, where data_dir = ${common_dir}/datasets; reproduce just that key
    base = OmegaConf.create({"common_dir": os.getcwd(), "data_dir": os.path.join(os.getcwd(), "datasets")})
    cfg = OmegaConf.merge(base, OmegaConf.load(cfg_path)); name = cfg.dataset_name
    if name in done: say("skip (already exported):", name); continue
    t0 = time.time()
    try:
        ds = instantiate(cfg.datamodule)
        idx = fast.get(name)
        idx = list(range(len(ds))) if idx is None else idx
        n = 0
        with open(OUT, "a") as f:
            for i in idx:
                p = ds[i]
                f.write(json.dumps({"dataset": name, "config": stem, "index": i, "question": p.question,
                                    "reference_answers": p.reference_answers, "should_abstain": p.should_abstain,
                                    "metadata": p.metadata}, default=str) + "\n"); n += 1
            f.flush(); os.fsync(f.fileno())
        say(f"ok {name} ({stem}): {n} items of {len(ds)} ({'subset' if name in fast else 'full'}) in {time.time()-t0:.0f}s")
    except Exception as e:
        say(f"FAIL {name} ({stem}): {type(e).__name__}: {str(e)[:300]}")
        log.write(traceback.format_exc()[-2000:] + "\n"); log.flush()
