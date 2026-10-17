#!/usr/bin/env python3
"""Main-campaign runner (PREREG_MAIN.md), derived from run_pilot.py with three changes: the corpus and R-gen budget are
parameters (M1, 1024 tokens), and the full answer-slot top 50 is stored per item (token id, token, unrounded logprob),
which the lane bridge check compares. Grading is run_pilot's, unchanged (imported).

One arm = one llama-server already up at --url.

Per P0 item:
  R-slot  the CAL prompt rendered by the server's own template with thinking OFF, plus `Exact Answer:`;
          /completion n_predict 1, n_probs 50, cache_prompt false, post_sampling_probs false.
          P_abs = P(" UNKNOWN") + P(" Unknown") + P(" unknown") from the top-50 (a missing variant counts 0).
  R-gen   /v1/chat/completions, greedy, thinking off, max_tokens --max-tokens (1024), cache_prompt false.
          Graded with the CAL rules (viability/run_fixture.py `abstain_key` + `ABSTAIN`, last `Exact Answer:`
          line, content preferred over reasoning, never concatenated).

Writes raw/main_<arm>.jsonl one row per item (flush + fsync); a re-run skips ids already written. The first
request after load is a discarded warm-up (server-uptime-is-a-variable).
"""
import argparse, json, math, os, re, sys, time, unicodedata
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "viability"))
from run_fixture import abstain_key, ABSTAIN, bare  # noqa: E402  (the CAL grader, reused unchanged)

FIX = json.load(open(HERE.parent / "viability" / "fixture_v0_beta.json"))
PROMPT = FIX["tier_cal"]["prompt"]
ANS = re.compile(r"Exact Answer\s*:\s*(.+?)(?:\n|$)", re.I | re.S)
VARIANTS = (" UNKNOWN", " Unknown", " unknown")
PROSE = re.compile(r"no such|does not exist|doesn't exist|not exist|fictional|no record|not a real|no known|not aware of",
                   re.I)
YEAR = re.compile(r"(?<!\d)(\d{3,4})(?!\d)")


from run_pilot import fold, surname, last_answer, grade, lenient  # noqa: E402  (grading unchanged)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--meta", default="{}", help="JSON recorded in the header row (model file, sha256, commit, flags)")
    ap.add_argument("--corpus", default="M1")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--expect-render-tail", default=None, help="the ceiling's render tail; a mismatch stops the arm")
    ap.add_argument("--expect-variants", default=None, help="the ceiling's UNKNOWN-variant ids (JSON)")
    ap.add_argument("--template-kwargs", default="{}", help="2026-10-16: JSON merged into chat_template_kwargs for every request (e.g. Beam's reasoning_effort); default {} leaves earlier arms unchanged")
    ap.add_argument("--skip-slot", action="store_true", help="2026-10-16: skip R-slot (P_abs recorded as null) for templates where a forced Exact Answer: after the generation prompt is off-distribution (Harmony)")
    ap.add_argument("--no-think-check", action="store_true", help="2026-10-16: skip the closed-</think> render check (Harmony templates have no </think>)")
    ap.add_argument("--usage", action="store_true", help="2026-10-17: record the generation's usage, timings and wall time per row (gen_usage, gen_tps, gen_elapsed_s); default off, so earlier arms are unchanged")
    ap.add_argument("--timeout", type=float, default=600, help="2026-10-17: HTTP timeout in seconds (default 600 as before; long reasoning budgets need more)")
    ap.add_argument("--thinking", action="store_true", help="2026-10-16: R-gen with enable_thinking true (R-slot stays thinking-off); default off, so earlier arms are unchanged")
    a = ap.parse_args()
    items = [json.loads(l) for l in open(HERE / "corpus" / f"{a.corpus}.jsonl")]
    out = HERE / "raw" / (f"main_{a.arm}.jsonl" if a.corpus == "M1" else f"main_{a.arm}.{a.corpus}.jsonl")
    out.parent.mkdir(exist_ok=True)
    done = {json.loads(l).get("id") for l in open(out)} if out.exists() else set()
    c = httpx.Client(timeout=a.timeout)

    # the answer-slot variants must be single tokens in THIS model's vocabulary, or P_abs is not what it claims
    vt = {v: c.post(f"{a.url}/tokenize", json={"content": "Exact Answer:" + v, "with_pieces": True}).json()["tokens"]
          for v in VARIANTS}
    base = c.post(f"{a.url}/tokenize", json={"content": "Exact Answer:"}).json()["tokens"]
    var_ids = {}
    for v, toks in vt.items():
        tail = toks[len(base):]
        var_ids[v] = tail[0]["id"] if len(tail) == 1 else None
    if None in var_ids.values():
        print("WARNING: a variant is not a single token after 'Exact Answer:':", var_ids, flush=True)

    def render(q):
        msgs = [{"role": "user", "content": PROMPT.format(q=q)}]
        return c.post(f"{a.url}/apply-template", json={"messages": msgs,
                      "chat_template_kwargs": {"enable_thinking": False, **json.loads(a.template_kwargs)}}).json()["prompt"]

    last_gen = {}

    def rgen(q):
        t0 = time.time()
        r = c.post(f"{a.url}/v1/chat/completions", json={
            "messages": [{"role": "user", "content": PROMPT.format(q=q)}], "temperature": 0, "max_tokens": a.max_tokens,
            "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": bool(a.thinking), **json.loads(a.template_kwargs)}})
        r.raise_for_status()
        d = r.json()
        last_gen.clear(); last_gen.update(usage=d.get("usage"), tps=(d.get("timings") or {}).get("predicted_per_second"),
                                          elapsed=round(time.time() - t0, 2))
        ch = d["choices"][0]
        return ch["message"].get("content") or "", ch["message"].get("reasoning_content") or "", ch["finish_reason"]

    tail0 = render("Q")[-60:]
    if a.expect_render_tail is not None and tail0 != a.expect_render_tail:
        sys.exit(f"render tail differs from the ceiling's: {tail0!r} != {a.expect_render_tail!r}")
    if a.expect_variants is not None and var_ids != json.loads(a.expect_variants):
        sys.exit(f"UNKNOWN variant ids differ from the ceiling's: {var_ids} != {a.expect_variants}")
    if not a.no_think_check and "</think>" not in render("Q"):
        sys.exit("thinking-off render has no closed think block")
    rgen("What is the capital of France?")        # discarded warm-up: the first request after a load is unreliable

    with open(out, "a") as f:
        if not done:
            p = render("Q")
            hdr = {"header": True, "arm": a.arm, "corpus": a.corpus, "max_tokens": a.max_tokens, "thinking": bool(a.thinking), "template_kwargs": json.loads(a.template_kwargs), "skip_slot": bool(a.skip_slot), **({"usage": True, "timeout": a.timeout} if a.usage else {}),
                   "meta": json.loads(a.meta), "variant_ids": var_ids,
                   "render_tail": p[-60:], "props": c.get(f"{a.url}/props").json().get("default_generation_settings", {}),
                   "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
            f.write(json.dumps(hdr, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
        for it in items:
            if it["id"] in done:
                continue
            P = render(it["question"])
            if not a.no_think_check and "</think>" not in P:
                print("WARNING: thinking-off render has no closed think block:", repr(P[-80:]), flush=True)
            if a.skip_slot:
                s, top, pv = {}, [], {v: None for v in VARIANTS}
            else:
                s = c.post(f"{a.url}/completion", json={"prompt": P + "Exact Answer:", "n_predict": 1, "n_probs": 50,
                            "temperature": 0, "cache_prompt": False, "post_sampling_probs": False}).json()
                top = s["completion_probabilities"][0]["top_logprobs"]
                pv = {v: next((math.exp(t["logprob"]) for t in top if t["id"] == var_ids[v]), 0.0) for v in VARIANTS}
            content, reasoning, fin = rgen(it["question"])
            got, nmatch, src = last_answer(content, reasoning)
            g = grade(it, got, fin, content)
            row = {"id": it["id"], "arm": it["arm"], "template": it["template"], "gold": it["gold"],
                   "P_abs": None if a.skip_slot else sum(pv.values()), "p_variants": pv, "slot_top": [(t["id"], t["token"], t["logprob"]) for t in top],
                   "slot_prompt_n": s.get("timings", {}).get("prompt_n"),
                   "content": content, "reasoning": reasoning, "finish": fin, "got": got, "n_answer_lines": nmatch,
                   "answer_src": src, "grade": g, "grade_lenient": lenient(it, got, g),
                   "prose_refusal": bool(g == "WRONG" and PROSE.search(got or ""))}
            if a.usage:
                row.update(gen_usage=last_gen.get("usage"), gen_tps=last_gen.get("tps"), gen_elapsed_s=last_gen.get("elapsed"))
            f.write(json.dumps(row, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
            pa = "  n/a" if row["P_abs"] is None else f"{row['P_abs']:.3f}"
            print(f"{it['id']}  P_abs={pa}  {g:10s} got={str(got)[:40]!r}  gold={it['gold']!r}", flush=True)


if __name__ == "__main__":
    main()
