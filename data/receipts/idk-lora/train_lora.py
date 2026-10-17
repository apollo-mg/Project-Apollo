#!/usr/bin/env python3
"""PREREG_IDK_LORA Stage B training (LORA and CTRL) on the RX 9070 XT, transformers + PEFT, bf16.

Data: raw/labels_G41.jsonl, `train` split only. known = CORRECT. LORA: the larger class is downsampled to the smaller
(seed 20261017); known -> the model's own response text, unknown -> "Exact Answer: UNKNOWN". CTRL: the same known items
and targets only. Prompt = the M1 prompt through the model's chat template; loss on the assistant tokens only.
LoRA r 16, alpha 32, dropout 0.05 on q/k/v/o/gate/up/down; AdamW lr 1e-4, cosine, 3 % warmup; 2 epochs; micro-batch 8
x accumulation 2 = effective 16; max length 384; LoRA weights in fp32 under bf16 autocast; seed 20261017.

Usage: train_lora.py {lora|ctrl} OUTDIR     -> OUTDIR/adapter (PEFT) + OUTDIR/train_log.json"""
import json, math, os, random, sys, time
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model

HERE = Path(__file__).resolve().parent; QA = HERE.parent / "quant-abstention"
BASE = "/mnt/TG_2TB/models_small/granite-4.1-3b"
PROMPT = json.load(open(QA.parent / "viability" / "fixture_v0_beta.json"))["tier_cal"]["prompt"]
SEED, R, ALPHA, DROP, LR, EPOCHS, MB, ACC, MAXLEN = 20261017, 16, 32, 0.05, 1e-4, 2, 8, 2, 384
UNK_TARGET = "Exact Answer: UNKNOWN"

mode, outdir = sys.argv[1], Path(sys.argv[2]); outdir.mkdir(parents=True, exist_ok=True)
random.seed(SEED); torch.manual_seed(SEED)
pool = {x["id"]: x for x in map(json.loads, open(HERE / "train_pool.jsonl"))}
lab = [r for r in map(json.loads, open(HERE / "raw" / "labels_G41.jsonl")) if r["split"] == "train"]
sys.path.insert(0, str(HERE)); from bare_rule import regrade   # Deviation 2: labels re-graded before balancing
for r in lab: r["grade"] = regrade(pool[r["id"]], r)
known = sorted([r for r in lab if r["grade"] == "CORRECT"], key=lambda r: r["id"])
unknown = sorted([r for r in lab if r["grade"] != "CORRECT"], key=lambda r: r["id"])
n = min(len(known), len(unknown))
if n < 300 and not os.environ.get("IDK_SMOKE"): sys.exit(f"stop rule: smaller class has {n} < 300 items")
rng = random.Random(SEED)
known_s, unknown_s = rng.sample(known, n), rng.sample(unknown, n)
data = [(pool[r["id"]]["question"], r["content"].strip()) for r in known_s]
if mode == "lora": data += [(pool[r["id"]]["question"], UNK_TARGET) for r in unknown_s]
elif mode != "ctrl": sys.exit("mode must be lora or ctrl")
rng.shuffle(data)
if os.environ.get("IDK_SMOKE"): data, EPOCHS = data[:32], 1   # code smoke test only; never used for an arm

tok = AutoTokenizer.from_pretrained(BASE)
def encode(q, a):
    msgs = [{"role": "user", "content": PROMPT.format(q=q)}]
    p = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    full = tok.apply_chat_template(msgs + [{"role": "assistant", "content": a}], tokenize=False)
    assert full.startswith(p), "chat template does not extend the generation prompt"
    pi = tok(p, add_special_tokens=False)["input_ids"]; fi = tok(full, add_special_tokens=False)["input_ids"][:MAXLEN]
    return fi, [-100] * len(pi) + fi[len(pi):]
enc = [encode(q, a) for q, a in data]

model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16).cuda()
model.gradient_checkpointing_enable(); model.enable_input_require_grads()
model = get_peft_model(model, LoraConfig(r=R, lora_alpha=ALPHA, lora_dropout=DROP, task_type="CAUSAL_LM",
                       target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
for p in model.parameters():
    if p.requires_grad: p.data = p.data.float()
params = [p for p in model.parameters() if p.requires_grad]
opt = torch.optim.AdamW(params, lr=LR, weight_decay=0.0)
steps = EPOCHS * math.ceil(len(enc) / (MB * ACC)); warm = max(1, int(0.03 * steps))
sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: (s + 1) / warm if s < warm else
                                          0.5 * (1 + math.cos(math.pi * (s - warm) / max(1, steps - warm))))
pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
log, t0, step = [], time.time(), 0
model.train()
for ep in range(EPOCHS):
    order = list(range(len(enc))); random.Random(SEED + ep).shuffle(order)
    for b0 in range(0, len(order), MB * ACC):
        opt.zero_grad(set_to_none=True); tot = 0.0
        chunk = order[b0:b0 + MB * ACC]
        for m0 in range(0, len(chunk), MB):
            batch = [enc[i] for i in chunk[m0:m0 + MB]]; L = max(len(x) for x, _ in batch)
            ids = torch.tensor([x + [pad] * (L - len(x)) for x, _ in batch]).cuda()
            lbl = torch.tensor([y + [-100] * (L - len(y)) for _, y in batch]).cuda()
            att = torch.tensor([[1] * len(x) + [0] * (L - len(x)) for x, _ in batch]).cuda()
            with torch.autocast("cuda", dtype=torch.bfloat16):
                loss = model(input_ids=ids, attention_mask=att, labels=lbl).loss * len(batch) / len(chunk)
            loss.backward(); tot += loss.item()
        torch.nn.utils.clip_grad_norm_(params, 1.0); opt.step(); sched.step(); step += 1
        log.append({"step": step, "epoch": ep, "loss": tot, "lr": sched.get_last_lr()[0], "t": round(time.time() - t0, 1)})
        if step % 20 == 0 or step == steps: print(log[-1], flush=True)
model.save_pretrained(outdir / "adapter")
json.dump({"mode": mode, "n_per_class": n, "known_total": len(known), "unknown_total": len(unknown),
           "examples": len(enc), "steps": steps, "seconds": round(time.time() - t0, 1), "log": log},
          open(outdir / "train_log.json", "w"), indent=1)
print("saved", outdir / "adapter", "examples", len(enc), "seconds", round(time.time() - t0, 1))
