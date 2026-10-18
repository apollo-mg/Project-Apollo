#!/usr/bin/env python3
"""PREREG_IDK_LORA2 generation steps against llama-server(s) of G41 Q8_0.

formats URL         : base answers in F2 and F3 for every known `train` item -> raw/formats_G41.jsonl (prose-graded).
smoke PLAIN_URL URL2: BASE through the two-adapter server (scales 0, 0) must equal a no-adapter server, byte for byte,
                      on 5 E2 items; exits 1 otherwise.
e2 URL2             : the 240 M1 questions in F4 (reworded) for BASE, LORA, LORA2 (explicit scales for both adapter ids:
                      id 0 = round 1 LORA, id 1 = LORA2) -> raw/E2_<ARM>.jsonl; then the 12 spot-check prompts (plain)
                      for LORA2 -> raw/normal_LORA2.jsonl.
"""
import json, os, sys
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent; QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(QA))
import prose_grade as pg            # noqa: E402
from bare_rule import regrade       # noqa: E402

F3_SUFFIX = "\nAnswer in a few words. If you are not confident, say that you don't know."
F4_SYSTEM, F4_SUFFIX = "You are a knowledgeable assistant.", " Please keep your answer brief."
SCALES = {"BASE": (0.0, 0.0), "LORA": (1.0, 0.0), "LORA2": (0.0, 1.0)}
c = httpx.Client(timeout=600)


def msgs(fmt, it):
    if fmt == "F2": return [{"role": "user", "content": it["question"]}]
    if fmt == "F3": return [{"role": "user", "content": it["question"] + F3_SUFFIX}]
    if fmt == "F4": return [{"role": "system", "content": F4_SYSTEM}, {"role": "user", "content": pg.paraphrase(it) + F4_SUFFIX}]
    raise ValueError(fmt)


def chat(url, m, max_tokens, scales=None):
    body = {"messages": m, "temperature": 0, "max_tokens": max_tokens, "cache_prompt": False}
    if scales is not None: body["lora"] = [{"id": 0, "scale": scales[0]}, {"id": 1, "scale": scales[1]}]
    d = c.post(f"{url}/v1/chat/completions", json=body).json()
    ch = d["choices"][0]
    return ch["message"].get("content") or "", ch["finish_reason"]


def formats(url):
    pool = {x["id"]: x for x in map(json.loads, open(HERE / "train_pool.jsonl"))}
    lab = [r for r in map(json.loads, open(HERE / "raw" / "labels_G41.jsonl")) if r["split"] == "train"]
    known = [r for r in lab if regrade(pool[r["id"]], r) == "CORRECT"]
    with open(HERE / "raw" / "formats_G41.jsonl", "w") as f:
        for r in known:
            it = pool[r["id"]]
            for fmt in ("F2", "F3"):
                content, fin = chat(url, msgs(fmt, it), 120)
                f.write(json.dumps({"id": it["id"], "fmt": fmt, "content": content, "finish": fin,
                                    "grade": pg.grade(dict(it, arm="T"), content)[0]}, ensure_ascii=False) + "\n")
    print("formats done", len(known), "known items")


def m1(): return [json.loads(l) for l in open(QA / "corpus" / "M1.jsonl")]


def smoke(plain, url2):
    for it in m1()[::48][:5]:
        a, _ = chat(plain, msgs("F4", it), 160); b, _ = chat(url2, msgs("F4", it), 160, SCALES["BASE"])
        print("SAME" if a == b else "DIFF", it["id"], repr(a[:60]))
        if a != b: sys.exit(1)
    print("SMOKE_OK")


def e2(url2):
    for arm, sc in SCALES.items():
        out = HERE / "raw" / f"E2_{arm}.jsonl"
        with open(out, "w") as f:
            for it in m1():
                content, fin = chat(url2, msgs("F4", it), 160, sc)
                s, l = pg.grade(it, content)
                f.write(json.dumps({"id": it["id"], "arm": it["arm"], "question_f4": pg.paraphrase(it), "content": content,
                                    "finish": fin, "strict": s, "lenient": l}, ensure_ascii=False) + "\n")
                f.flush(); os.fsync(f.fileno())
        print("E2", arm, "done")
    spot = [json.loads(l) for l in open(HERE / "raw" / "spotcheck" / "spotcheck.jsonl")]
    with open(HERE / "raw" / "normal_LORA2.jsonl", "w") as f:
        for r in spot:
            content, fin = chat(url2, [{"role": "user", "content": r["q"]}], 120, SCALES["LORA2"])
            f.write(json.dumps({"kind": r["kind"], "q": r["q"], "content": content,
                                "refused": bool(pg.REFUSE.search(content))}, ensure_ascii=False) + "\n")
    print("normal done")


if __name__ == "__main__":
    {"formats": lambda: formats(sys.argv[2]), "smoke": lambda: smoke(sys.argv[2], sys.argv[3]),
     "e2": lambda: e2(sys.argv[2])}[sys.argv[1]]()
