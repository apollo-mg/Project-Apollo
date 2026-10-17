#!/usr/bin/env python3
"""Post-registration checks for RESULT_IDK_LORA.md's correction (2026-10-17, review before reporting; not registered):
real-question net per arm and the refuse-everything reference; base-vs-LoRA grade cross-tab within template x group
(does the LoRA refuse what the base got wrong, or just obscure templates?); answer-slot / certainty AUROC on the base's
labels; and, exploratory (chosen on M1), IBM's certainty answering the LoRA's number of real questions."""
import json, sys, collections
sys.path.insert(0, "."); from analyze_idk import load, ARMS, auroc
items = {x["id"]: x for x in map(json.loads, open("../quant-abstention/corpus/M1.jsonl"))}
R = {k: load(k, {}, items) for k in ARMS}
real = [i for i in items if items[i]["arm"] != "U"]
print("refuse-all Net", round(100 / 240, 3))
for k in ARMS:
    c = sum(R[k][i]["grade"] == "CORRECT" for i in real); w = sum(R[k][i]["grade"] == "WRONG" for i in real)
    print(f"{k:9s} real-question net {c - w:+4d} (correct {c}, wrong {w})")
for t in ("capital", "novel", "opera", "university"):
    for g in "EH":
        ids = [i for i in real if items[i]["template"] == t and items[i]["arm"] == g]
        bc = [i for i in ids if R["IDK_B41"][i]["grade"] == "CORRECT"]; bw = [i for i in ids if R["IDK_B41"][i]["grade"] == "WRONG"]
        ref = lambda xs: sum(R["IDK_LORA"][i]["grade"] == "ABSTAINED" for i in xs)
        print(f"{t:10s} {g}: base-correct {len(bc):2d} -> LoRA refuses {ref(bc):2d} | base-wrong {len(bw):2d} -> LoRA refuses {ref(bw):2d}")
print("all real:", dict(sorted(collections.Counter(f"{R['IDK_B41'][i]['grade']}->{R['IDK_LORA'][i]['grade']}" for i in real).items())))
lab = lambda i: R["IDK_B41"][i]["grade"] == "CORRECT"
for k, f in (("IDK_B41", lambda i: R["IDK_B41"][i]["P_abs"]), ("IDK_LORA", lambda i: R["IDK_LORA"][i]["P_abs"]),
             ("IDK_IBM", lambda i: 1 - R["IDK_IBM"][i]["certainty"])):
    print(f"{k} AUROC on base labels, real items: {auroc([f(i) for i in real if not lab(i)], [f(i) for i in real if lab(i)]):.3f}")
cov = sum(R["IDK_LORA"][i]["grade"] in ("CORRECT", "WRONG") for i in real)
top = sorted(real, key=lambda i: -R["IDK_IBM"][i]["certainty"])[:cov]
c = sum(R["IDK_IBM"][i]["base_grade"] == "CORRECT" for i in top); w = sum(R["IDK_IBM"][i]["base_grade"] == "WRONG" for i in top)
print(f"EXPLORATORY: IBM answering its top {cov} real questions: correct {c}, wrong {w}, net {c - w:+d}")
