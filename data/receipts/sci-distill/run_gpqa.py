#!/usr/bin/env python3
"""PREREG_SCI_DISTILL.md: GPQA Diamond (198 items, local HF cache, offline) with thinking on, in rounds.

Each round asks every item once. The choice order is a permutation seeded by (item, round), identical across arms.
Prompt: OpenAI simple-evals' multiple-choice template; the answer is the LAST "ANSWER: X" in the content (not the
reasoning). No answer, or finish=length, counts as wrong in the primary analysis.
Requests go to every server in --urls at once, --slots per server; one dispatcher hands out work strictly in order,
round by round, so rounds finish in order. No request starts after --deadline (epoch seconds).

GPQA must not be published: full text goes ONLY to --private (outside the repo, flush+fsync per row). The repo file
--public holds the item's sha256 prefix, round, correctness, answered, finish and token counts: no text, no letters.
Resumable: (item, round) pairs already in --public are skipped.
Usage: run_gpqa.py --arm A --urls U1,U2 --rounds 1-4 --public F --private F [--slots 4] [--max-tokens 30000]"""
import argparse, hashlib, json, os, queue, random, re, threading, time
from concurrent.futures import ThreadPoolExecutor
import httpx

TEMPLATE = ("Answer the following multiple choice question. The last line of your response should be of the following "
            "format: 'ANSWER: $LETTER' (without quotes) where LETTER is one of ABCD. Think step by step before "
            "answering.\n\n{q}\n\nA) {a}\nB) {b}\nC) {c}\nD) {d}")
ANSWER = re.compile(r"(?i)Answer[ \t]*:[ \t]*\$?([A-D])\$?")
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5, "repeat_penalty": 1.0}


def items():
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1"); os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from datasets import load_dataset
    d = load_dataset("Idavidrein/gpqa", "gpqa_diamond", split="train")
    out = []
    for r in d:
        q = r["Question"].strip()
        out.append({"id": hashlib.sha256(q.encode()).hexdigest()[:16], "q": q, "domain": r["High-level domain"],
                    "choices": [r["Correct Answer"].strip()] + [r[f"Incorrect Answer {k}"].strip() for k in (1, 2, 3)]})
    assert len(out) == 198 and len({i["id"] for i in out}) == 198
    return out


def render(item, rnd):
    """(prompt, correct letter, seed) for an item in a round; the same in every arm."""
    h = int(hashlib.sha256(f"{item['id']}:{rnd}".encode()).hexdigest()[:8], 16)
    order = list(range(4)); random.Random(h).shuffle(order)
    ch = [item["choices"][k] for k in order]
    return TEMPLATE.format(q=item["q"], a=ch[0], b=ch[1], c=ch[2], d=ch[3]), "ABCD"[order.index(0)], h % (2 ** 31)


def grade(content, gold):
    m = ANSWER.findall(content or "")
    return (m[-1].upper() if m else None), bool(m) and m[-1].upper() == gold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True); ap.add_argument("--urls", required=True)
    ap.add_argument("--rounds", default="1-4"); ap.add_argument("--slots", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=30000); ap.add_argument("--timeout", type=float, default=10800)
    ap.add_argument("--public", required=True); ap.add_argument("--private", required=True)
    ap.add_argument("--deadline", type=float, default=0); ap.add_argument("--meta", default="{}")
    a = ap.parse_args()
    lo, hi = map(int, a.rounds.split("-"))

    def urls():   # "@FILE" is re-read on every slot search, so servers can join a running arm
        if a.urls.startswith("@"):
            return [u.strip() for u in open(a.urls[1:]) if u.strip()]
        return a.urls.split(",")
    its = items()
    done = set()
    if os.path.exists(a.public):
        for l in open(a.public):
            r = json.loads(l)
            if not r.get("header"): done.add((r["id"], r["round"]))
    else:
        with open(a.public, "w") as f:
            f.write(json.dumps({"header": True, "arm": a.arm, "sampling": SAMPLING, "max_tokens": a.max_tokens,
                                "thinking": True, "template": "simple-evals multichoice", "meta": json.loads(a.meta),
                                "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}) + "\n")
    work = [(rnd, it) for rnd in range(lo, hi + 1) for it in its if (it["id"], rnd) not in done]
    lock = threading.Lock(); cl = httpx.Client(timeout=a.timeout)
    free, known = queue.Queue(), set()   # one token (the server URL) per free slot

    def refresh():   # servers listed since the last look join with --slots tokens each
        for u in urls():
            if u not in known:
                known.add(u)
                for _ in range(a.slots):
                    free.put(u)
    print(f"{a.arm}: {len(work)} requests to run ({len(done)} already done)", flush=True)

    def one(job, u):
        rnd, it = job
        try:
            prompt, gold, seed = render(it, rnd); t0 = time.time()
            try:
                r = cl.post(f"{u}/v1/chat/completions", json={
                    "messages": [{"role": "user", "content": prompt}], "max_tokens": a.max_tokens, "seed": seed,
                    "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": True}, **SAMPLING}).json()
                ch = r["choices"][0]; m = ch["message"]; usage = r.get("usage", {})
                content, reasoning, finish, err = m.get("content") or "", m.get("reasoning_content") or "", ch.get("finish_reason"), None
            except Exception as e:   # recorded as an error row; rerun to retry it
                content = reasoning = ""; finish = None; usage = {}; err = repr(e)[:300]
        finally:
            free.put(u)
        if err:
            print(f"{a.arm} r{rnd} {it['id']}: ERROR {err}", flush=True); return
        got, ok = grade(content, gold)
        pub = {"id": it["id"], "round": rnd, "domain": it["domain"], "correct": ok, "answered": got is not None,
               "finish": finish, "completion_tokens": usage.get("completion_tokens"), "prompt_tokens": usage.get("prompt_tokens"),
               "reasoning_chars": len(reasoning), "content_chars": len(content), "elapsed_s": round(time.time() - t0, 1),
               "server": u}
        prv = {**pub, "gold": gold, "got": got, "seed": seed, "content": content, "reasoning": reasoning}
        with lock:
            for path, row in ((a.private, prv), (a.public, pub)):
                with open(path, "a") as f:
                    f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
        print(f"{a.arm} r{rnd} {it['id']} {'OK ' if ok else 'BAD'} {finish} {usage.get('completion_tokens')} tok "
              f"{pub['elapsed_s']} s", flush=True)

    # 2026-11-10 (PREREG_SCI_DISTILL.md Deviation 2): one dispatcher hands out jobs strictly in work order, each only once
    # it holds a free slot, and checks the deadline at that moment. Before, idle workers raced for slots, so a job could
    # wait for hours behind later ones and start after the deadline.
    futs = []
    with ThreadPoolExecutor(max_workers=a.slots * 8) as ex:
        for job in work:
            while True:
                refresh()
                try:
                    u = free.get(timeout=1.0); break
                except queue.Empty:
                    continue
            if a.deadline and time.time() > a.deadline:
                free.put(u); print(f"{a.arm}: deadline passed, {len(work) - len(futs)} requests not started", flush=True); break
            futs.append(ex.submit(one, job, u))
        for f in futs:
            f.result()


if __name__ == "__main__":
    main()
