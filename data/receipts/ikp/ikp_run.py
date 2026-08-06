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

REASONING MODELS: pass --no-think.
Recall is not a reasoning task, and a <think> chain under --max-tokens truncates into a probe that
was never answered. An empty or truncated response scores as a REFUSAL or a WRONG, either of which
manufactures a knowledge deficit out of a token budget. `finish_reason` is captured for exactly this
reason and ikp_score.py buckets it as NO_ANSWER rather than folding it into accuracy.

Usage:
  ./ikp_run.py --endpoint http://127.0.0.1:8091 --label bf16 --out ikp_bf16.jsonl
  ./ikp_run.py --endpoint http://127.0.0.1:8091 --label tq4_1s --tiers T1,T2,T3,T4 --concurrency 4

  # reasoning model, with the Phase-0 gating precondition enforced before any inference
  ./ikp_run.py --endpoint http://127.0.0.1:8091 --label glm-base --out ikp_glm_base.jsonl \
      --no-think --assert-load-log glm_base_load.log --require-gating sigmoid
"""
import argparse, json, os, queue, re, sys, threading, time, urllib.request

SYSTEM_MSG = "Answer factual questions directly and concisely. If you don't know, say 'I don't know'."


def post(endpoint, payload, timeout=120):
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def assert_gating(load_log, expect):
    """Phase-0 precondition (Lab_Spec §G-1a). ABORT, do not warn.

    A GGUF that omits `expert_gating_func` is resolved by a hardcoded compatibility heuristic in
    llama.cpp (`src/models/deepseek2.cpp`: n_layer in {47,48} && n_vocab == 154880 -> sigmoid, else
    softmax). Two arms of one comparison can therefore end up on DIFFERENT gating functions with no
    error emitted -- and for an expert-pruning study, routing is the mechanism under test.

    So we never infer it from source; we read the runtime's own print_info back (standard §1).
    """
    if not load_log:
        return None
    if not os.path.exists(load_log):
        sys.exit(f"[ikp] FATAL: --assert-load-log {load_log} does not exist. "
                 f"Capture the server/CLI load output and pass it here.")
    with open(load_log, errors="replace") as f:
        found = re.findall(r"expert_gating_func\s*=\s*(\w+)", f.read())
    if not found:
        sys.exit(f"[ikp] FATAL: no 'expert_gating_func' line in {load_log}. "
                 f"Load with -v so print_info is emitted; a missing line is not a pass.")
    got = {g.lower() for g in found}
    if len(got) > 1:
        sys.exit(f"[ikp] FATAL: {load_log} reports multiple gating functions {sorted(got)}.")
    got = got.pop()
    if expect and got != expect.lower():
        sys.exit(f"[ikp] FATAL: gating function is '{got}', expected '{expect}'. "
                 f"Arms on different gating functions are not comparable.")
    return got


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
                    help="match llama-server -np; >1 only valid if the server has slots. "
                         "NOTE: >1 changes batch composition and can break run-to-run determinism")
    ap.add_argument("--limit", type=int, default=0, help="debug: stop after N probes")
    ap.add_argument("--no-think", action="store_true",
                    help="disable the model's reasoning mode via chat_template_kwargs "
                         "{'enable_thinking': false}. Recall is not a reasoning task, and a <think> "
                         "chain under --max-tokens truncates into an unanswered probe")
    ap.add_argument("--chat-template-kwargs", default=None,
                    help="raw JSON passed through as chat_template_kwargs, for models whose "
                         "thinking toggle is spelled differently. Overrides --no-think")
    ap.add_argument("--assert-load-log", default=None,
                    help="path to the arm's llama-server/llama-cli load output (captured with -v). "
                         "Checked before any inference runs")
    ap.add_argument("--require-gating", default=None,
                    help="e.g. 'sigmoid'. Abort unless --assert-load-log reports this gating "
                         "function. Both arms of a comparison must report the same one")
    args = ap.parse_args()

    gating = assert_gating(args.assert_load_log, args.require_gating)
    if gating:
        print(f"[ikp] gate G-1a: expert_gating_func = {gating} (from {args.assert_load_log})",
              file=sys.stderr)

    ctk = None
    if args.chat_template_kwargs:
        ctk = json.loads(args.chat_template_kwargs)
    elif args.no_think:
        ctk = {"enable_thinking": False}

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
            if ctk:
                payload["chat_template_kwargs"] = ctk
            resp, err = "", None
            finish, n_out, reasoning = None, None, None
            t1 = time.time()
            for attempt in range(3):
                try:
                    d = post(args.endpoint, payload)
                    ch = d["choices"][0]
                    msg = ch.get("message") or {}
                    resp = (msg.get("content") or "").strip()
                    # finish_reason == "length" means the generation hit max_tokens: the probe was
                    # never answered. Scoring that as WRONG (or as a refusal, which is what an empty
                    # string looks like) manufactures a knowledge deficit out of a token budget --
                    # the exact false positive the Puzzle-75B HumanEval+ gap turned out to be.
                    finish = ch.get("finish_reason")
                    # some builds split the <think> chain into its own field; keep its length only
                    rc = msg.get("reasoning_content")
                    reasoning = len(rc) if rc else None
                    n_out = (d.get("usage") or {}).get("completion_tokens")
                    err = None
                    break
                except Exception as e:                       # noqa: BLE001
                    err = f"{type(e).__name__}: {e}"
                    time.sleep(2 * (attempt + 1))
            rec = {"id": p["id"], "tier": p["tier"], "label": args.label,
                   "question": p["question"], "gold": p["answer"],
                   "source_type": p.get("source_type"), "domain": p.get("domain"),
                   "response": resp, "error": err, "latency_s": round(time.time() - t1, 2),
                   "finish_reason": finish, "completion_tokens": n_out,
                   "reasoning_chars": reasoning}
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
    errs = trunc = total = 0
    with open(args.out) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            total += 1
            if r.get("error"):
                errs += 1
            if r.get("finish_reason") == "length":
                trunc += 1
    print(f"\n[ikp] {args.label}: done in {time.time()-t0:.0f}s, {errs} errored, "
          f"{trunc}/{total} truncated ({trunc/max(total,1):.1%})", file=sys.stderr)
    # §1: positive verification -- prove the measurement ran, do not assume it.
    if total == 0:
        sys.exit("[ikp] FATAL: 0 records written. The run did not happen.")
    if trunc / total > 0.02:
        print(f"[ikp] WARNING: {trunc/total:.1%} of probes hit max_tokens={args.max_tokens}. "
              f"With reasoning mode on this is the expected failure -- pass --no-think, or raise "
              f"--max-tokens. Accuracy from this run is not interpretable as recall.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
