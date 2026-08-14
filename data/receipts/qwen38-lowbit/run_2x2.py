#!/usr/bin/env python3
"""Qwen 3.8 27B low-bit 2x2: {IQ2_M, IQ3_XXS} x {thinking on, off}.

Records finish_reason per response, not just text. battle16gb Finding 5 is the
reason: a panel misattributed cap-deaths to silent closure because lm-eval never
logged a stop reason, and the 25pp Puzzle gap turned out to be a stopping-rule
failure rather than an answering failure. A score without its stop reason is not
a result here.

Serves one model at a time (16 GB card), so the caller launches/kills the server
between model arms. Both thinking arms hit the same loaded server.
"""
import json, os, re, sys, time, urllib.request

HOST = os.environ.get("HOST", "http://127.0.0.1:8082")

# Fixed set, identical across all four cells. Mix of: short factual (cheap to
# grade), a reasoning item, a format-following item, and a known loop-bait
# (open-ended enumeration) because loop-detector exists for a reason.
PROMPTS = [
    ("factual",   "What is the capital of Australia? Answer in one word."),
    ("arith",     "A shelf holds 3 boxes. Each box holds 7 jars. Each jar holds 12 marbles. How many marbles total? Show your arithmetic, then give the number."),
    ("format",    "List exactly three primary colors, one per line, no other text."),
    ("reason",    "A train leaves at 14:20 and arrives at 17:05. It stops twice for 8 minutes each. What is its moving time? Give the answer as H:MM."),
    ("code",      "Write a Python function is_palindrome(s) that ignores case and non-alphanumeric characters. Code only."),
    ("loopbait",  "Name the planets of the solar system in order from the sun. Stop when you have named them all."),
    ("refuse",    "What is 1/0? Answer briefly."),
    ("longform",  "Explain in at most 4 sentences why quantizing a neural network can degrade output quality."),
]


def ask(prompt, thinking, n_predict=512, timeout=300):
    body = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "top_k": 1,
        "seed": 1234,
        "n_predict": n_predict,
        "chat_template_kwargs": {"enable_thinking": bool(thinking)},
    }
    req = urllib.request.Request(
        f"{HOST}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    dt = time.time() - t0
    ch = d["choices"][0]
    return {
        "text": ch["message"]["content"],
        # THE point of this harness: why did generation stop?
        "finish_reason": ch.get("finish_reason"),
        "completion_tokens": d.get("usage", {}).get("completion_tokens"),
        "prompt_tokens": d.get("usage", {}).get("prompt_tokens"),
        "wall_s": round(dt, 2),
    }


def looks_looped(text, min_rep=4):
    """Cheap repetition detector — a line or sentence repeated >= min_rep times."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for l in set(lines):
        if len(l) > 8 and lines.count(l) >= min_rep:
            return True
    return False


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    out_dir = os.path.dirname(os.path.abspath(__file__))
    results = []
    for thinking in (True, False):
        for name, prompt in PROMPTS:
            try:
                r = ask(prompt, thinking)
                r.update(prompt_name=name, thinking=thinking, model=tag,
                         looped=looks_looped(r["text"]))
            except Exception as e:
                r = dict(prompt_name=name, thinking=thinking, model=tag,
                         error=f"{type(e).__name__}: {e}")
            results.append(r)
            fr = r.get("finish_reason", "ERR")
            n = r.get("completion_tokens", "?")
            flag = " LOOP" if r.get("looped") else ""
            print(f"  {tag:12s} think={str(thinking):5s} {name:9s} "
                  f"finish={str(fr):10s} tok={n}{flag}", flush=True)
    path = os.path.join(out_dir, f"raw_{tag}.json")
    json.dump(results, open(path, "w"), indent=1)
    # Summary that leads with stop reasons, since that is the finding at risk.
    print(f"\n=== {tag} stop-reason census ===")
    for th in (True, False):
        arm = [r for r in results if r.get("thinking") is th]
        reasons = {}
        for r in arm:
            reasons[r.get("finish_reason", "ERR")] = reasons.get(r.get("finish_reason", "ERR"), 0) + 1
        loops = sum(1 for r in arm if r.get("looped"))
        toks = [r.get("completion_tokens") or 0 for r in arm]
        print(f"  thinking={th}: {reasons}  loops={loops}  "
              f"mean_tok={sum(toks)//max(1,len(toks))}")
    print(f"-> {path}")


if __name__ == "__main__":
    main()
