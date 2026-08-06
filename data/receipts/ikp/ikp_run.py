#!/usr/bin/env python3
"""Run the IKP knowledge probes against a local llama-server (OpenAI-compatible endpoint).

Separates INFERENCE from SCORING on purpose: this script only generates and stores raw responses.
Scoring lives in ikp_score.py and can be re-run any number of times -- with a different scorer, a
different refusal rule, or an LLM judge -- without paying for inference again. Given a 7-arm quant
ladder that is the difference between one pass and seven.

Methodology is matched to Bojie Li's ikp_estimate.py (19PINE-AI/ikp) so numbers stay comparable:
  system message : "Answer factual questions directly and concisely. If you don't know, say 'I don't know'."
  temperature    : 0
  gold answers   : ';' separates ALTERNATIVES -- any one counts as correct

Tier guidance (see CONTENT_NOTES / receipts for the reasoning):
  T1/T2  near ceiling on an unquantized 27B (99.5% / 97.5%) -- useful only as a "did it break" check
  T3/T4  THE SIGNAL (78.5% / 38% baseline) -- real headroom, mixed sources
  T5-T7  DROPPED by default. Two independent reasons: baseline accuracy is 10%/3%/4% (at the noise
         floor for the *unquantized* model, so there is almost nothing to lose), and they draw
         100% from researcher+wikidata, the two sources the replication audit flagged worst
         (researcher 24.9% of probes ambiguous/incorrect, wikidata 8.08%).

Usage:
  ./ikp_run.py --endpoint http://127.0.0.1:8091 --label bf16 --out ikp_bf16.jsonl
  ./ikp_run.py --endpoint http://127.0.0.1:8091 --label tq4_1s --tiers T1,T2,T3,T4 --concurrency 4
"""
import argparse, json, os, queue, sys, threading, time, urllib.request

SYSTEM_MSG = "Answer factual questions directly and concisely. If you don't know, say 'I don't know'."


def post(endpoint, payload, timeout=120):
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True, help="llama-server base URL, e.g. http://127.0.0.1:8091")
    ap.add_argument("--label", required=True, help="arm name recorded in the output (e.g. tq4_1s)")
    ap.add_argument("--probes", default="ikp_probes.json")
    ap.add_argument("--out", required=True, help="JSONL of raw responses (resumable)")
    ap.add_argument("--tiers", default="T1,T2,T3,T4",
                    help="comma list; default drops T5-T7 (noise floor + audit-flagged sources)")
    ap.add_argument("--max-tokens", type=int, default=64,
                    help="answers average 1.5 words; 64 is generous and catches rambling")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--concurrency", type=int, default=1,
                    help="match llama-server -np; >1 only valid if the server has slots")
    ap.add_argument("--limit", type=int, default=0, help="debug: stop after N probes")
    args = ap.parse_args()

    tiers = {t.strip() for t in args.tiers.split(",") if t.strip()}
    probes = [p for p in json.load(open(args.probes)) if p["tier"] in tiers]
    if args.limit:
        probes = probes[: args.limit]

    done = set()
    if os.path.exists(args.out):
        with open(args.out) as f:
            for line in f:
                try:
                    done.add(json.loads(line)["id"])
                except Exception:
                    pass
    todo = [p for p in probes if p["id"] not in done]
    print(f"[ikp] {args.label}: {len(probes)} probes in {sorted(tiers)}, "
          f"{len(done)} already done, {len(todo)} to run", file=sys.stderr)
    if not todo:
        return

    lock = threading.Lock()
    out = open(args.out, "a")
    q = queue.Queue()
    for p in todo:
        q.put(p)
    counter = [0]
    t0 = time.time()

    def worker():
        while True:
            try:
                p = q.get_nowait()
            except queue.Empty:
                return
            payload = {
                "messages": [{"role": "system", "content": SYSTEM_MSG},
                             {"role": "user", "content": p["question"]}],
                "temperature": args.temperature,
                "max_tokens": args.max_tokens,
                "stream": False,
            }
            resp, err = "", None
            t1 = time.time()
            for attempt in range(3):
                try:
                    d = post(args.endpoint, payload)
                    resp = (d["choices"][0]["message"].get("content") or "").strip()
                    err = None
                    break
                except Exception as e:                       # noqa: BLE001
                    err = f"{type(e).__name__}: {e}"
                    time.sleep(2 * (attempt + 1))
            rec = {"id": p["id"], "tier": p["tier"], "label": args.label,
                   "question": p["question"], "gold": p["answer"],
                   "source_type": p.get("source_type"), "domain": p.get("domain"),
                   "response": resp, "error": err, "latency_s": round(time.time() - t1, 2)}
            with lock:
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                counter[0] += 1
                n = counter[0]
                if n % 25 == 0 or n == len(todo):
                    el = time.time() - t0
                    print(f"\r  [{n}/{len(todo)}] {el:.0f}s elapsed, "
                          f"{n/el:.2f} probes/s, eta {(len(todo)-n)/max(n/el,1e-9):.0f}s",
                          end="", file=sys.stderr)

    ts = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, args.concurrency))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    out.close()
    errs = 0
    with open(args.out) as f:
        for line in f:
            try:
                if json.loads(line).get("error"):
                    errs += 1
            except Exception:
                pass
    print(f"\n[ikp] {args.label}: done in {time.time()-t0:.0f}s, {errs} errored", file=sys.stderr)


if __name__ == "__main__":
    main()
