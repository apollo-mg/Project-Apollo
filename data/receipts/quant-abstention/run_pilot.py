#!/usr/bin/env python3
"""Pilot runner (PREREG_PILOT.md + Deviations 1-3): one arm = one llama-server already up at --url.

Per P0 item:
  R-slot  the CAL prompt rendered by the server's own template with thinking OFF, plus `Exact Answer:`;
          /completion n_predict 1, n_probs 50, cache_prompt false, post_sampling_probs false.
          P_abs = P(" UNKNOWN") + P(" Unknown") + P(" unknown") from the top-50 (a missing variant counts 0).
  R-gen   /v1/chat/completions, greedy, thinking off, max_tokens 256, cache_prompt false.
          Graded with the CAL rules (viability/run_fixture.py `abstain_key` + `ABSTAIN`, last `Exact Answer:`
          line, content preferred over reasoning, never concatenated).

Writes raw/pilot_<arm>.jsonl one row per item (flush + fsync); a re-run skips ids already written. The first
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


def fold(s):
    """Grading normalization (prereg + Deviation 2): case, punctuation, diacritics, a leading 'The'."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().casefold().strip()
    s = re.sub(r"\s*\([^)]*\)", "", s)          # a trailing parenthetical is commentary, not the name
    s = re.sub(r"^the\s+", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def surname(name):
    return fold(re.sub(r"\s*\([^)]*\)", "", name).split()[-1]) if name.split() else ""


def last_answer(content, reasoning):
    for src in (content, reasoning):             # content first; the two are never concatenated
        m = ANS.findall(src or "")
        if m:
            return m[-1].strip(), len(m), "content" if src is content else "reasoning"
    return None, 0, None


def grade(it, got, finish, content):
    if not (content or "").strip():
        return "INVALID"
    if got is None:
        return "TRUNCATED" if finish == "length" else "NO-ANSWER"
    if not bare(got):
        return "NO-ANSWER"
    if abstain_key(got) in ABSTAIN:
        return "ABSTAINED"
    if it["arm"] == "U":
        return "WRONG"
    if it["template"] in ("novel", "university"):
        ys = {str(int(y)) for y in YEAR.findall(got)}
        return "CORRECT" if ys == {it["gold"]} else "WRONG"
    names = it.get("gold_aliases") or [it["gold"]]
    ok = {fold(n) for n in names}
    if it["template"] == "opera":                # person gold: the bare surname alone also matches
        ok |= {surname(n) for n in names}
    return "CORRECT" if fold(got) in ok else "WRONG"


def lenient(it, got, g):
    if g != "WRONG" or it["template"] not in ("novel", "university") or it["arm"] == "U":
        return g
    ys = {str(int(y)) for y in YEAR.findall(got or "")}
    return "CORRECT" if len(ys) == 1 and ys <= set(it.get("gold_years_lenient", [])) else "WRONG"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--meta", default="{}", help="JSON recorded in the header row (model file, sha256, commit, flags)")
    a = ap.parse_args()
    items = [json.loads(l) for l in open(HERE / "corpus" / "P0.jsonl")]
    out = HERE / "raw" / f"pilot_{a.arm}.jsonl"
    out.parent.mkdir(exist_ok=True)
    done = {json.loads(l).get("id") for l in open(out)} if out.exists() else set()
    c = httpx.Client(timeout=600)

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
                      "chat_template_kwargs": {"enable_thinking": False}}).json()["prompt"]

    def rgen(q):
        r = c.post(f"{a.url}/v1/chat/completions", json={
            "messages": [{"role": "user", "content": PROMPT.format(q=q)}], "temperature": 0, "max_tokens": 256,
            "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}})
        r.raise_for_status()
        ch = r.json()["choices"][0]
        return ch["message"].get("content") or "", ch["message"].get("reasoning_content") or "", ch["finish_reason"]

    rgen("What is the capital of France?")        # discarded warm-up: the first request after a load is unreliable

    with open(out, "a") as f:
        if not done:
            p = render("Q")
            hdr = {"header": True, "arm": a.arm, "meta": json.loads(a.meta), "variant_ids": var_ids,
                   "render_tail": p[-60:], "props": c.get(f"{a.url}/props").json().get("default_generation_settings", {}),
                   "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
            f.write(json.dumps(hdr, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
        for it in items:
            if it["id"] in done:
                continue
            P = render(it["question"])
            if "</think>" not in P:
                print("WARNING: thinking-off render has no closed think block:", repr(P[-80:]), flush=True)
            s = c.post(f"{a.url}/completion", json={"prompt": P + "Exact Answer:", "n_predict": 1, "n_probs": 50,
                        "temperature": 0, "cache_prompt": False, "post_sampling_probs": False}).json()
            top = s["completion_probabilities"][0]["top_logprobs"]
            pv = {v: next((math.exp(t["logprob"]) for t in top if t["id"] == var_ids[v]), 0.0) for v in VARIANTS}
            content, reasoning, fin = rgen(it["question"])
            got, nmatch, src = last_answer(content, reasoning)
            g = grade(it, got, fin, content)
            row = {"id": it["id"], "arm": it["arm"], "template": it["template"], "gold": it["gold"],
                   "P_abs": sum(pv.values()), "p_variants": pv, "slot_top": [(t["token"], round(t["logprob"], 4)) for t in top[:10]],
                   "slot_prompt_n": s.get("timings", {}).get("prompt_n"),
                   "content": content, "reasoning": reasoning, "finish": fin, "got": got, "n_answer_lines": nmatch,
                   "answer_src": src, "grade": g, "grade_lenient": lenient(it, got, g),
                   "prose_refusal": bool(g == "WRONG" and PROSE.search(got or ""))}
            f.write(json.dumps(row, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
            print(f"{it['id']}  P_abs={row['P_abs']:.3f}  {g:10s} got={str(got)[:40]!r}  gold={it['gold']!r}", flush=True)


if __name__ == "__main__":
    main()
