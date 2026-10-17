#!/usr/bin/env python3
"""PREREG_IDK_LORA Stage B arm IBM: IBM's granitelib-core uncertainty LoRA (granite-4.1-3b/lora), as its card documents.

For each (question, base answer): messages [user: the M1 prompt, assistant: G41's own answer, user: "<certainty>"],
the generation prompt, then the prefix `{"score": "`. certainty = sum_d P(d) (0.1 d + 0.05) over the ten digit tokens,
normalised over the digits (the card's likelihood mapping). transformers + PEFT, bf16, on the RX 9070 XT.
A format check first: greedy generation on five calib items must produce {"score": "<digit>"}.

calib: base answers from raw/labels_G41.jsonl (calib split) -> tau from 0.05..0.95 step 0.025 maximising Net
       (+1 CORRECT, -1 WRONG, 0 otherwise; refusal below tau = 0); ties -> lowest tau. -> fit_ibm.json
M1:    base answers from quant-abstention/raw/main_IDK_B41.jsonl -> raw/IDK_IBM.jsonl (grade = ABSTAINED below tau).
Usage: ibm_arm.py"""
import json, time, sys
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

HERE = Path(__file__).resolve().parent; QA = HERE.parent / "quant-abstention"
BASE = "/mnt/TG_2TB/models_small/granite-4.1-3b"
ADAPTER = "/mnt/TG_2TB/models_small/granitelib-core-r1.0/uncertainty/granite-4.1-3b/lora"
PROMPT = json.load(open(QA.parent / "viability" / "fixture_v0_beta.json"))["tier_cal"]["prompt"]
PREFIX, BS = '{"score": "', 16

tok = AutoTokenizer.from_pretrained(BASE, padding_side="left")
model = PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16).cuda(), ADAPTER).eval()
digits = [tok.encode(PREFIX + str(d), add_special_tokens=False)[len(tok.encode(PREFIX, add_special_tokens=False))] for d in range(10)]
assert len(set(digits)) == 10, digits
vals = torch.tensor([0.1 * d + 0.05 for d in range(10)])


def render(q, a, prefix=True):
    m = [{"role": "user", "content": PROMPT.format(q=q)}, {"role": "assistant", "content": a}, {"role": "user", "content": "<certainty>"}]
    return tok.apply_chat_template(m, tokenize=False, add_generation_prompt=True) + (PREFIX if prefix else "")


@torch.no_grad()
def certainty(pairs):
    out = []
    for i in range(0, len(pairs), BS):
        enc = tok([render(q, a) for q, a in pairs[i:i + BS]], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
        logits = model(**enc).logits[:, -1, :].float()
        p = torch.softmax(logits[:, digits], dim=-1).cpu()
        out += (p * vals).sum(-1).tolist()
    return out


sys.path.insert(0, str(HERE)); from bare_rule import regrade   # Deviation 2: base grades re-graded
pool = {x["id"]: x for x in map(json.loads, open(HERE / "train_pool.jsonl"))}
calib = [r for r in map(json.loads, open(HERE / "raw" / "labels_G41.jsonl")) if r["split"] == "calib"]
for r in calib: r["grade"] = regrade(pool[r["id"]], r)
with torch.no_grad():   # format check, as the card shows it (no prefix)
    for r in calib[:5]:
        enc = tok(render(pool[r["id"]]["question"], r["content"], prefix=False), return_tensors="pt", add_special_tokens=False).to("cuda")
        g = tok.decode(model.generate(**enc, max_new_tokens=15, do_sample=False)[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        print("format check:", repr(g)); assert g.strip().startswith('{"score": "') and g.strip()[11].isdigit(), g

t0 = time.time()
cc = certainty([(pool[r["id"]]["question"], r["content"]) for r in calib]); t_cal = time.time() - t0
grid = [round(0.05 + 0.025 * k, 3) for k in range(37)]
def net(tau, rows, cs): return sum(0 if c < tau else {"CORRECT": 1, "WRONG": -1}.get(r["grade"], 0) for r, c in zip(rows, cs)) / len(rows)
table = [{"tau": t, "net": net(t, calib, cc)} for t in grid]
best = max(table, key=lambda x: (round(x["net"], 9), -x["tau"]))
tau = best["tau"]
items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
base = [r for r in map(json.loads, open(QA / "raw" / "main_IDK_B41.jsonl")) if "id" in r]
for r in base: r["grade"] = regrade(items[r["id"]], r)
t0 = time.time()
cm = certainty([(items[r["id"]]["question"], r["content"]) for r in base]); t_m1 = time.time() - t0
with open(HERE / "raw" / "IDK_IBM.jsonl", "w") as f:
    for r, c in zip(base, cm):
        f.write(json.dumps({"id": r["id"], "arm": items[r["id"]]["arm"], "base_grade": r["grade"], "certainty": c,
                            "grade": "ABSTAINED" if c < tau else r["grade"], "tau": tau}) + "\n")
ntok = sum(len(tok(render(items[r["id"]]["question"], r["content"]), add_special_tokens=False)["input_ids"]) for r in base)
json.dump({"tau": tau, "calib_net": best["net"], "n_calib": len(calib), "table": table, "seconds_calib": round(t_cal, 1),
           "seconds_m1": round(t_m1, 1), "m1_second_pass_prompt_tokens_total": ntok, "batch": BS},
          open(HERE / "fit_ibm.json", "w"), indent=1)
print("tau", tau, "calib Net", round(best["net"], 4), "M1 second pass", round(t_m1, 1), "s,", ntok, "prompt tokens")
