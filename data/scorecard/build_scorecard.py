#!/usr/bin/env python3
"""Model scorecard: a long-format results database DERIVED from committed receipts (the receipts stay the source of
truth). One row per (model config, instrument, metric). New instruments add rows, never columns.
Sources: M1 raw rows (data/receipts/quant-abstention/raw/main_*.jsonl, graded by run_main.py) and AbstentionBench
text-free verdict tables (data/receipts/abstentionbench/verdicts_*.csv). Identity comes from registry.json (hand-run
models) and recipes/*.json (models run through the pipeline, abstend.py).
Outputs: scorecard.db (SQLite, gitignored), scorecard.csv (committed, diffable), cards.json (one card per model).
Usage: build_scorecard.py"""
import csv, json, math, re, sqlite3
from pathlib import Path
HERE = Path(__file__).resolve().parent; R = HERE.parent / "receipts"
REG = json.load(open(HERE / "registry.json"))
from abstend import load_recipes; load_recipes(REG)   # recipes/*.json: models run through the pipeline

def wilson(k, n, z=1.96):
    if not n: return (None, None, None)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(p, 4), round(max(0, c - h), 4), round(min(1, c + h), 4))

rows = []   # (config_id, model, instrument, metric, value, lo, hi, n, receipt)
configs = {}
def add(cfg, inst, metric, k, n, receipt):
    v, lo, hi = wilson(k, n); rows.append((cfg, configs[cfg]["model"], inst, metric, v, lo, hi, n, receipt))

# --- M1 (quant-abstention instrument, 240 items: E 40 easy, H 100 hard real, U 100 invented) ---
bare = lambda r: r.get("grade") == "NO-ANSWER" and re.fullmatch(r"\W*unknown\W*", (r.get("content") or "").strip(), re.I) is not None
for arm, a in REG["m1_arms"].items():
    f = R / "quant-abstention" / "raw" / f"main_{arm}.jsonl"
    if not f.exists(): continue
    lines = [json.loads(l) for l in open(f)]; hdr = lines[0]; it = [x for x in lines[1:] if "id" in x]
    cfg = f"m1:{arm}"
    configs[cfg] = {"config_id": cfg, "model": a["model"], "quant": a["quant"], "thinking": a["thinking"], "primary": a["primary"], "note": a["note"],
                    "decoding": "sampled " + json.dumps(hdr["sampling"]) if hdr.get("sampling") else "greedy",
                    "template_kwargs": json.dumps(hdr.get("template_kwargs", {})), "system": hdr.get("system", ""), "started": hdr.get("started", ""),
                    "source": f"quant-abstention/raw/main_{arm}.jsonl"}
    G = {g: [x for x in it if x["id"].startswith(f"M1-{g}-")] for g in "EHU"}
    src = configs[cfg]["source"]; inst = "M1-v1"
    add(cfg, inst, "knowledge.easy_acc", sum(x["grade"] == "CORRECT" for x in G["E"]), len(G["E"]), src)
    add(cfg, inst, "knowledge.hard_acc", sum(x["grade"] == "CORRECT" for x in G["H"]), len(G["H"]), src)
    add(cfg, inst, "honesty.overabstain_hard", sum(x["grade"] == "ABSTAINED" for x in G["H"]), len(G["H"]), src)
    add(cfg, inst, "honesty.invented_refusal", sum(x["grade"] == "ABSTAINED" for x in G["U"]), len(G["U"]), src)
    add(cfg, inst, "honesty.invented_refusal_lenient", sum(x["grade"] == "ABSTAINED" or bare(x) for x in G["U"]), len(G["U"]), src)
    add(cfg, inst, "honesty.invented_confabulation", sum(x["grade"] == "WRONG" for x in G["U"]), len(G["U"]), src)
    add(cfg, inst, "reliability.unfinished", sum(x["grade"] == "TRUNCATED" or (x["grade"] == "INVALID" and x.get("finish") == "length") for x in it), len(it), src)

# --- AbstentionBench fast subset (2,004 items), norefs judge (primary per Addendum 1) ---
CONTEXT_REMOVED = {"GSM8K", "MMLUMath", "MMLUHistory", "GPQA"}; FALSE_PREMISE = {"FalseQADataset", "QAQADataset"}
def abench(arm, path, col):
    cfg = f"abench:{arm}"; a = REG["abench_arms"][arm]
    configs[cfg] = {"config_id": cfg, "model": a["model"], "quant": a["quant"], "thinking": a["thinking"], "primary": a["primary"], "note": a["note"],
                    "decoding": "T 0.8, top_p 0.95 (Meta)", "template_kwargs": "", "system": "", "started": "", "source": f"abstentionbench/{path.name}"}
    V = [r for r in csv.DictReader(open(path)) if r[col] != ""]
    sa = [r for r in V if r["should_abstain"] == "1"]; called = [r for r in V if r[col] == "1"]
    inst = "AbstentionBench-fast/norefs"; src = configs[cfg]["source"]
    add(cfg, inst, "honesty.abstention_recall", sum(r[col] == "1" for r in sa), len(sa), src)
    add(cfg, inst, "honesty.abstention_precision", sum(r["should_abstain"] == "1" for r in called), len(called), src)
    for name, S in (("honesty.missing_info_recall", CONTEXT_REMOVED), ("honesty.false_premise_recall", FALSE_PREMISE)):
        sub = [r for r in sa if r["dataset"] in S]; add(cfg, inst, name, sum(r[col] == "1" for r in sub), len(sub), src)
abench("LLAMA8", R / "abstentionbench" / "verdicts_LLAMA8.csv", "norefs")
abench("Q27OFF", R / "abstentionbench" / "verdicts_Q27.csv", "off_norefs")
abench("Q27ON", R / "abstentionbench" / "verdicts_Q27.csv", "on_norefs")

# --- write ---
db = HERE / "scorecard.db"; db.unlink(missing_ok=True); con = sqlite3.connect(db)
con.execute("create table models (model_id text primary key, display text, developer text, arch text, total_b real, active_b real, lineage text)")
con.execute("create table configs (config_id text primary key, model_id text, quant text, thinking text, decoding text, template_kwargs text, system text, primary_card int, note text, started text, source text)")
con.execute("create table results (config_id text, model_id text, instrument text, metric text, value real, ci_lo real, ci_hi real, n int, receipt text)")
for k, m in REG["models"].items(): con.execute("insert into models values (?,?,?,?,?,?,?)", (k, m["display"], m["developer"], m["arch"], m["total_b"], m["active_b"], m["lineage"]))
for c in configs.values(): con.execute("insert into configs values (?,?,?,?,?,?,?,?,?,?,?)", (c["config_id"], c["model"], c["quant"], c["thinking"], c["decoding"], c["template_kwargs"], c["system"], int(c["primary"]), c["note"], c["started"], c["source"]))
con.executemany("insert into results values (?,?,?,?,?,?,?,?,?)", rows); con.commit()
with open(HERE / "scorecard.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["config_id", "model_id", "quant", "thinking", "decoding", "instrument", "metric", "value", "ci_lo", "ci_hi", "n", "receipt"])
    for r in sorted(rows): c = configs[r[0]]; w.writerow([r[0], r[1], c["quant"], c["thinking"], c["decoding"], r[2], r[3], r[4], r[5], r[6], r[7], r[8]])
cards = {}
for k, m in REG["models"].items():
    cs = [c for c in configs.values() if c["model"] == k]
    if not cs: continue
    card = {**m, "model_id": k, "configs": []}
    for c in sorted(cs, key=lambda c: (not c["primary"], c["config_id"])):
        card["configs"].append({**{x: c[x] for x in ("config_id", "quant", "thinking", "decoding", "primary", "note", "source")},
                                "metrics": {f"{r[2]}|{r[3]}": {"v": r[4], "lo": r[5], "hi": r[6], "n": r[7]} for r in rows if r[0] == c["config_id"]}})
    cards[k] = card
json.dump(cards, open(HERE / "cards.json", "w"), indent=1)
print(f"{len(REG['models'])} models, {len(configs)} configs, {len(rows)} result rows -> scorecard.db / scorecard.csv / cards.json")
