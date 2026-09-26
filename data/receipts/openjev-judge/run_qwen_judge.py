#!/usr/bin/env python3
"""PREREG_OPENJEV_JUDGE.md: Qwen3.8-27B as a fixed-choice judge on the same 77 items, same premises, same wordings.

  run_qwen_judge.py --url http://127.0.0.1:8230

One /v1/chat/completions call per (item, condition, wording, option order): thinking off, reasoning_effort medium
(injects nothing), max_tokens 1, temperature 0, cache_prompt false, top_logprobs 20. P(letter) sums the first
token's top_logprobs whose text is that letter. P(ask) per order = P(ask letter) / (P(A) + P(B)); the item's P(ask)
is the mean over both orders (removes letter-position bias; OpenJev is order-free by construction).
Gate G5: P(A) + P(B) >= 0.9 on every call, else the model is not answering the fixed choice. One warmup call is
discarded first (the first request after a load is unreliable).
"""
import argparse, hashlib, json, math, os, sys, time
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_items import REGISTERED  # noqa: E402

USER_FRAME = "{premise}\n\nQuestion: {instr}\n{lines}\nAnswer with the letter only."


def lines_for(w, order):
    rub = w["rubric"]
    return "\n".join(f"{L}) {o}: {rub[o]}" if rub else f"{L}) {o}" for L, o in zip("AB", order))


def ask_llm(cli, url, content):
    body = {"messages": [{"role": "user", "content": content}], "max_tokens": 1, "temperature": 0, "seed": 1,
            "logprobs": True, "top_logprobs": 20, "cache_prompt": False,
            "chat_template_kwargs": {"enable_thinking": False, "reasoning_effort": "medium"}}
    r = cli.post(f"{url}/v1/chat/completions", json=body)
    r.raise_for_status()
    c = r.json()["choices"][0]
    top = c["logprobs"]["content"][0]["top_logprobs"]
    p = {L: sum(math.exp(t["logprob"]) for t in top if t["token"].strip() == L) for L in "AB"}
    return p, c["logprobs"]["content"][0]["token"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8230")
    ap.add_argument("--tag", default="qwen38-27b-iq3xxs")
    a = ap.parse_args()
    out = HERE / "raw" / f"judge_{a.tag}.jsonl"
    items = [json.loads(l) for l in open(HERE / "items.jsonl")]
    cli = httpx.Client(timeout=600)
    props = cli.get(f"{a.url}/props").json()
    meta = {"tag": a.tag, "model_path": props.get("model_path"), "build": props.get("build_info"),
            "user_frame_sha256": hashlib.sha256(USER_FRAME.encode()).hexdigest()}
    w0 = REGISTERED["W1"]
    ask_llm(cli, a.url, USER_FRAME.format(premise=items[0]["premise_world"], instr=w0["instructions"],
                                          lines=lines_for(w0, w0["options"])))   # warmup, discarded
    print(json.dumps(meta), flush=True)
    done = set()
    if out.exists():
        done = {(r["id"], r["cond"], r["wording"]) for r in map(json.loads, open(out)) if r.get("id")}
    t0 = time.time()
    with open(out, "a") as f:
        if not done:
            f.write(json.dumps({"meta": meta}) + "\n")
        for it in items:
            for cond in ("world", "reqonly"):
                for wk, w in REGISTERED.items():
                    if (it["id"], cond, wk) in done:
                        continue
                    per = []
                    for order in (w["options"], w["options"][::-1]):
                        content = USER_FRAME.format(premise=it[f"premise_{cond}"], instr=w["instructions"],
                                                    lines=lines_for(w, order))
                        p, tok = ask_llm(cli, a.url, content)
                        mass = p["A"] + p["B"]
                        L_ask = "AB"[order.index(w["ask_option"])]
                        per.append({"order": order, "pA": p["A"], "pB": p["B"], "mass": mass, "top_token": tok,
                                    "p_ask": p[L_ask] / mass if mass > 0 else float("nan")})
                    row = {"id": it["id"], "cluster": it["cluster"], "gold": it["gold"], "cond": cond, "wording": wk,
                           "p_ask": sum(x["p_ask"] for x in per) / 2, "orders": per}
                    f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
                    print(f"{it['id']:28s} {cond:7s} {wk} gold={it['gold']} p_ask={row['p_ask']:.3f} "
                          f"mass={min(x['mass'] for x in per):.3f}", flush=True)
    print(f"done in {time.time() - t0:.0f}s -> {out}")


if __name__ == "__main__":
    main()
