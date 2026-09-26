#!/usr/bin/env python3
"""PREREG_OPENJEV_JUDGE.md: score the 77 argus judge items with one OpenJev checkpoint.

  run_openjev.py --ckpt /mnt/TG_2TB/AI/Models/openjev/qwen3.5-4b-nli-v5 --code /path/with/modeling_openjev.py+openjev_decide.py

Load gates run first and abort the run on failure (a checkpoint whose head silently random-initialises still returns
clean softmaxes):
  G1  no "newly initialized" / missing-key warning while loading
  G2  the card's refund demo (4B v5 card value 0.07): P(yes) < 0.25
  G3  MNLI validation_matched, first 200 rows: accuracy >= 0.75 (card 0.896 for 4B v5; random head ~0.33)
  G4  no scored pair reaches max_len (right truncation would cut the hypothesis, which comes last)

Scoring is OpenJev's own decide() path (openjev_decide.py): one hypothesis per option,
'The answer to "{instr}" is {label}: {crit}', P(entailment) normalised over the options. The raw
[contradiction, entailment, neutral] triple of every pair is kept, and every decide() result is cross-checked
against the triples. One row per (item, condition, wording), appended with fsync.
"""
import argparse, json, logging, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_items import REGISTERED  # noqa: E402

MNLI_TO_OJ = {0: 1, 1: 2, 2: 0}   # MNLI (ent, neu, con) -> OpenJev order (con, ent, neu)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--code", required=True, help="dir holding modeling_openjev.py and openjev_decide.py (pinned rev)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    sys.path.insert(0, a.code)

    import numpy as np
    import torch
    import transformers
    msgs = []

    class Grab(logging.Handler):
        def emit(self, rec):
            msgs.append(rec.getMessage())
    transformers.logging.set_verbosity_warning()
    transformers.logging.get_logger().addHandler(Grab())

    from modeling_openjev import ENT, OpenJevCrossEncoder
    import openjev_decide as od

    tag = Path(a.ckpt).name
    out = Path(a.out or HERE / "raw" / f"openjev_{tag}.jsonl")
    t0 = time.time()
    ce = OpenJevCrossEncoder(a.ckpt, device="cuda")
    jev = od.OpenJev(ce)
    meta = {"tag": tag, "ckpt": a.ckpt, "torch": torch.__version__, "hip": torch.version.hip,
            "transformers": transformers.__version__, "device": torch.cuda.get_device_name(0),
            "dtype": str(next(ce.model.parameters()).dtype), "max_len": ce.max_len, "load_s": round(time.time() - t0, 1)}

    # G1
    # match the load report's own phrases, not every message containing "missing" (a rope-config validation
    # notice, "Missing validation function ... rope_type", is not a weight-load problem)
    keys = ("newly initialized", "missing keys", "were not used", "unexpected keys", "not initialized")
    bad = [m for m in msgs if any(k in m.lower() for k in keys)]
    meta["G1_load_warnings"] = bad
    assert not bad, f"G1 FAIL: {bad}"
    # and the direct probe: the loaded score head must equal the checkpoint's tensor
    from safetensors import safe_open
    with safe_open(str(Path(a.ckpt) / "model.safetensors"), "pt") as st:
        k = next(k for k in st.keys() if k.endswith("score.weight"))
        ref = st.get_tensor(k)
    got = ce.model.score.weight.detach().to("cpu", ref.dtype)
    meta["G1_score_head_equal"] = bool(torch.equal(got, ref))
    assert meta["G1_score_head_equal"], "G1 FAIL: score head differs from the checkpoint"
    # G2
    refund = jev.decide("Policy: refunds require a receipt and purchase within 30 days. The customer bought 12 days ago "
                        "but has no receipt.",
                        [{"type": "noul", "instructions": "Under the stated policy, is a refund permitted?",
                          "options": ["no", "yes"]}])[0]["noul"]
    meta["G2_refund_p_yes"] = round(refund, 4)
    assert refund < 0.25, f"G2 FAIL: refund P(yes) {refund}"
    # G3
    mnli = json.load(open(HERE / "raw/mnli_vm_200.json"))
    p = ce.predict([(r["premise"], r["hypothesis"]) for r in mnli])
    acc = float(np.mean([int(p[i].argmax()) == MNLI_TO_OJ[r["label"]] for i, r in enumerate(mnli)]))
    meta["G3_mnli200_acc"] = round(acc, 4)
    assert acc >= 0.75, f"G3 FAIL: MNLI-200 accuracy {acc}"

    items = [json.loads(l) for l in open(HERE / "items.jsonl")]
    # G4
    longest = 0
    for it in items:
        for cond in ("world", "reqonly"):
            for w in REGISTERED.values():
                for o in w["options"]:
                    crit = (w["rubric"] or {}).get(o, o)
                    h = od.TEMPLATE.format(instr=w["instructions"], label=o, crit=crit)
                    n = len(ce.tok(ce.template.format(premise=it[f"premise_{cond}"].strip(), hypothesis=h.strip()))["input_ids"])
                    longest = max(longest, n)
            assert len(it[f"premise_{cond}"]) <= od.WINDOW_CHARS   # one window, so decide() == the triples below
    meta["G4_longest_pair_tokens"] = longest
    assert longest < ce.max_len, f"G4 FAIL: {longest} >= {ce.max_len}"
    print(json.dumps(meta), flush=True)

    done = set()
    if out.exists():
        for l in open(out):
            r = json.loads(l)
            if r.get("id"):
                done.add((r["id"], r["cond"], r["wording"]))
    with open(out, "a") as f:
        if not done:
            f.write(json.dumps({"meta": meta}) + "\n")
        for it in items:
            for cond in ("world", "reqonly"):
                for wk, w in REGISTERED.items():
                    if (it["id"], cond, wk) in done:
                        continue
                    instr = w["instructions"] + (od.RUBRIC_MARK + json.dumps(w["rubric"]) if w["rubric"] else "")
                    q = {"type": "choice", "instructions": instr, "options": w["options"]}
                    dec = jev.decide(it[f"premise_{cond}"], [q])[0]["probabilities"]
                    crits = w["rubric"] or {o: o for o in w["options"]}
                    hyps = [od.TEMPLATE.format(instr=w["instructions"], label=o, crit=crits[o]) for o in w["options"]]
                    tri = ce.predict([(it[f"premise_{cond}"], h) for h in hyps])
                    ent = tri[:, ENT] / tri[:, ENT].sum()
                    for o, e in zip(w["options"], ent):
                        assert abs(dec[o] - float(e)) < 1e-4, (it["id"], cond, wk, dec, ent.tolist())
                    row = {"id": it["id"], "cluster": it["cluster"], "gold": it["gold"], "cond": cond, "wording": wk,
                           "p_ask": dec[w["ask_option"]], "decide": dec,
                           "triples": {o: [round(float(x), 6) for x in t] for o, t in zip(w["options"], tri)}}
                    f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
    print(f"done {tag} in {time.time() - t0:.0f}s -> {out}")


if __name__ == "__main__":
    main()
