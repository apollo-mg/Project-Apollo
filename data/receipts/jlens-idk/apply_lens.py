#!/usr/bin/env python3
"""PREREG_JLENS_IDK readout: apply the Granite 4.1 3B Jacobian lens to BASE, LORA and LORA2 (adapters merged into the
bf16 weights) at the last prompt token of each M1 question in round 2's E2 setting (F4 wrapper, reworded question).

Per item and arm: the rank (0 = top-1) of each U-set token at every lens layer, with the Jacobian (J-lens) and without
(logit lens); the model's own top-1 next token and the lens top-1 at the last source layer (sanity gate); and the top-10
lens tokens at layer 20 (descriptive). -> raw/lens_<ARM>.jsonl
Usage: apply_lens.py"""
import json, sys
from pathlib import Path
import torch, transformers, jlens
from peft import PeftModel

HERE = Path(__file__).resolve().parent; IDK = HERE.parent / "idk-lora"; QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(IDK)); import prose_grade as pg   # noqa: E402
BASE = "/mnt/TG_2TB/models_small/granite-4.1-3b"; ADP = "/mnt/TG_2TB/models_small/idk_adapters"
LENS = "/mnt/TG_2TB/models_small/jlens/granite41_wikitext100.pt"
USET = [" unknown", " Unknown", " UNKNOWN", " unsure", " uncertain", " unclear", " fictional", " nonexistent", " sorry", " Sorry"]
F4_SYSTEM, F4_SUFFIX = "You are a knowledgeable assistant.", " Please keep your answer brief."

tok = transformers.AutoTokenizer.from_pretrained(BASE)
uids = [tok.encode(w, add_special_tokens=False) for w in USET]
assert all(len(u) == 1 for u in uids), uids
uids = [u[0] for u in uids]
lens = jlens.JacobianLens.load(LENS)
items = [json.loads(l) for l in open(QA / "corpus" / "M1.jsonl")]
(HERE / "raw").mkdir(exist_ok=True)


def render(it):
    m = [{"role": "system", "content": F4_SYSTEM}, {"role": "user", "content": pg.paraphrase(it) + F4_SUFFIX}]
    return tok.apply_chat_template(m, tokenize=False, add_generation_prompt=True)


def ranks(logits):   # logits [vocab] -> rank of each U-set token
    order = logits.float().argsort(descending=True)
    pos = torch.empty_like(order); pos[order] = torch.arange(len(order), device=order.device)
    return [int(pos[u]) for u in uids]


for arm in ("BASE", "LORA", "LORA2"):
    hf = transformers.AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16).cuda()
    if arm != "BASE":
        hf = PeftModel.from_pretrained(hf, f"{ADP}/{arm.lower()}/adapter").merge_and_unload()
    hf.eval(); model = jlens.from_hf(hf, tok)
    last = lens.source_layers[-1]
    with open(HERE / "raw" / f"lens_{arm}.jsonl", "w") as f, torch.no_grad():
        for it in items:
            p = render(it)
            jl, ml, ids = lens.apply(model, p, positions=[-1], max_seq_len=512)
            ll, _, _ = lens.apply(model, p, positions=[-1], max_seq_len=512, use_jacobian=False)
            row = {"id": it["id"], "arm": it["arm"], "template": it["template"],
                   "jrank": {L: ranks(v[0]) for L, v in jl.items()}, "lrank": {L: ranks(v[0]) for L, v in ll.items()},
                   "model_top1": tok.decode([int(ml[0].argmax())]), "lens_top1_last": tok.decode([int(jl[last][0].argmax())]),
                   "top10_L20": [tok.decode([int(t)]) for t in jl[20][0].topk(10).indices] if 20 in jl else None}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(arm, "done", flush=True)
    del model, hf; torch.cuda.empty_cache()
