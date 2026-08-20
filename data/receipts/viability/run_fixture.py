#!/usr/bin/env python3
"""Run the Apollo viability fixture against a llama-server endpoint.

Tier 1 is a GATE: any failure means the stack is broken, not the model.
Tier 2 is a GATE on the model/quant/sampling being sane.
Reports per-tier pass/fail plus the structural outcome of each item.
"""
import argparse, collections, json, math, os, re, sys, urllib.request

PROMPT = ("{q}\n\nThink briefly if you need to, then end your reply with exactly one line:\n"
          "Exact Answer: <your answer>")
ANS = re.compile(r"Exact Answer\s*:\s*(.+?)(?:\n|$)", re.I | re.S)

def norm(s):
    s = (s or "").strip().lower().rstrip(".")
    s = re.sub(r"[\s,]+", "", s)
    return s

def bare(s):
    """norm() plus the markdown a model wraps its answer in."""
    return norm(s).strip("*_`\"'")

_PUNCT = re.compile(r"[^a-z0-9/]")

_MIXED = re.compile(r"(?<![\d./])(\d+)\s+(\d+)\s*/\s*(\d+)(?![\d./])")
_FRAC  = re.compile(r"(?<![\d./])(\d+)\s*/\s*(\d+)(?![\d./])")
_NUM   = re.compile(r"[-+]?\d*\.?\d+")

def numeric_values(text):
    """Every distinct number in `text`, understanding mixed numbers and fractions.

    Returns None if there are none. Mixed/fraction spans are consumed first so
    '66 2/3' reads as one value (66.667), not three.
    """
    t = (text or "").replace(",", "")
    vals = []
    for rx, fn in ((_MIXED, lambda m: int(m[1]) + int(m[2]) / int(m[3])),
                   (_FRAC,  lambda m: int(m[1]) / int(m[2]))):
        out = []
        for m in rx.finditer(t):
            try: vals.append(fn(m))
            except ZeroDivisionError: return None
            out.append((m.start(), m.end()))
        for a, b in reversed(out):
            t = t[:a] + " " + t[b:]
    for m in _NUM.finditer(t):
        try: vals.append(float(m.group()))
        except ValueError: pass
    return vals or None

def answer_matches(got, gold):
    """Exact first, then a UNIT-TOLERANT numeric compare.

    Dry run 01: the model answered '72 minutes', '2560 bytes', 'UDP 123' and '66 2/3 km'
    — all correct, all scored FAIL, because norm() strips whitespace and a trailing period
    but not a unit. On the calibration arm that turned a right answer into ANSWERED-WRONG,
    the same cell confabulation lands in.

    Deliberately conservative: the numeric path fires only when the reply contains EXACTLY
    ONE distinct number. 'not 72 but 80' carries two and falls through to a miss rather than
    matching the first one it sees.
    """
    if bare(got) == bare(gold):
        return True
    gv = numeric_values(gold)
    if not gv or len(set(gv)) != 1:
        return False
    av = numeric_values(got)
    if not av or len({round(v, 6) for v in av}) != 1:
        return False
    return math.isclose(av[0], gv[0], rel_tol=1e-3, abs_tol=1e-9)

def abstain_key(s):
    """Aggressive fold, used ONLY for the abstention check — never for the correctness
    compare. Deliberately more permissive than `bare`: scoring a genuine refusal as an
    answer inflates the CONFABULATION rate, which is this tier's headline number, so
    errors here have to fall the other way. ("I don't know" -> "idontknow".)"""
    return _PUNCT.sub("", norm(s))

# The tier_cal prompt NAMES "UNKNOWN" as a sanctioned reply, so abstention is a token match,
# not a semantic judgement. These aliases absorb formatting noise only. A model that abstains
# in prose instead of using the offered token scores ANSWERED-WRONG, deliberately: the tier
# measures use of an offered hatch, which is what AA's non-hallucination metric measures too.
# Tiers 1-2 keep the old keyword whitelist and are NOT comparable on this axis.
ABSTAIN = {"unknown", "n/a", "na", "none", "unanswerable", "cannotbedetermined",
           "cannotdetermine", "cannotbeanswered", "notapplicable", "nosuchthing",
           "doesnotexist", "idontknow"}

def classify(got, gold):
    """Three-way, applied IDENTICALLY to both arms — that identity is the whole point.
    The old grader folded 'abstained' and 'confabulated' into one FAIL on the answerable
    arm, which is exactly the distinction a calibration 2x2 is made of."""
    g = bare(got)
    if not g:
        return "NO-ANSWER"
    if abstain_key(got) in ABSTAIN:
        return "ABSTAINED"
    if gold != "UNKNOWN" and answer_matches(got, gold):
        return "ANSWERED-CORRECT"
    return "ANSWERED-WRONG"


JSONL = None    # set from --jsonl; opened append, flushed per item
EFFORT = None   # set from --effort; passed via chat_template_kwargs, the dial Qwen3.8 honours

TPS_FLOOR = 2.5   # assumed worst-case decode rate; .194 measured 7.7 tok/s on a 27B Q6_K

def ask(host, q, n_predict=512, timeout=None, prompt=None):
    if timeout is None:
        timeout = 300 + n_predict / TPS_FLOOR
    body = {"messages": [{"role": "user", "content": (prompt or PROMPT).format(q=q)}],
            "temperature": 0, "top_k": 1, "n_predict": n_predict}
    if EFFORT:
        body["chat_template_kwargs"] = {"reasoning_effort": EFFORT}
    req = urllib.request.Request(host.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    m = d["choices"][0]["message"]
    fin = d["choices"][0].get("finish_reason", "")
    return (m.get("content") or ""), (m.get("reasoning_content") or ""), fin

def pick_answer(content, reasoning, fin):
    """Returns (answer, n_matches). LAST match wins and `content` is preferred over
    `reasoning` — never concatenated. Both guards exist because the tier instruction names
    the answer format: an echo of the format, or an abandoned draft, sits BEFORE the real
    answer, so first-match parsing reads the wrong line. B2 measured 43 % of disputed parses
    carrying multiple `Exact Answer:` strings; this is that detector, carried over.

    n_matches > 1 means the PARSE is suspect, not the model. It is reported, never silently
    resolved."""
    for text in (content, reasoning if fin != "length" else ""):
        ms = ANS.findall(text or "")
        if ms:
            return ms[-1].strip(), len(ms)
    return "", 0

def record(**row):
    """Append one item's outcome to the JSONL sidecar and flush immediately."""
    if JSONL is None:
        return
    JSONL.write(json.dumps(row, ensure_ascii=False) + "\n")
    JSONL.flush()
    os.fsync(JSONL.fileno())

def extract_json(text):
    """Pull the first JSON value out of a reply. Tolerates ``` fences and leading prose,
    because those are formatting noise, not the syntax failure we are testing for."""
    t = re.sub(r"```(?:json)?", "", text).strip()
    # Whichever bracket appears FIRST wins. Trying "{" unconditionally made an array of
    # objects parse as its first element (dry run 02, TS-02).
    openers = sorted((("{", "}"), ("[", "]")),
                     key=lambda oc: (t.find(oc[0]) if t.find(oc[0]) >= 0 else len(t) + 1))
    for opener, closer in openers:
        i = t.find(opener)
        if i < 0: continue
        depth = 0
        for j in range(i, len(t)):
            if t[j] == opener: depth += 1
            elif t[j] == closer:
                depth -= 1
                if depth == 0:
                    try: return json.loads(t[i:j+1])
                    except Exception: break
    return None

def check_struct(obj, chk):
    """Structural grading: parse + schema. Never string match."""
    if obj is None: return False, "unparseable"
    if chk.get("type") == "array":
        if not isinstance(obj, list): return False, f"not an array ({type(obj).__name__})"
        if "len" in chk and len(obj) != chk["len"]: return False, f"len {len(obj)} != {chk['len']}"
        if "exact" in chk and obj != chk["exact"]: return False, "contents differ"
        for el in obj:
            for k in chk.get("each_keys", []):
                if not isinstance(el, dict) or k not in el: return False, f"missing key {k}"
        return True, "ok"
    if not isinstance(obj, dict): return False, f"not an object ({type(obj).__name__})"
    for k, v in chk.get("keys", {}).items():
        if k not in obj: return False, f"missing key {k!r}"
        if obj[k] != v: return False, f"{k}={obj[k]!r} want {v!r}"
    for parent, sub in chk.get("nested", {}).items():
        if parent not in obj or not isinstance(obj[parent], dict):
            return False, f"missing/!object {parent!r}"
        for k, v in sub.items():
            if k not in obj[parent]: return False, f"missing {parent}.{k}"
            if obj[parent][k] != v: return False, f"{parent}.{k}={obj[parent][k]!r} want {v!r}"
    if "nested_empty" in chk:
        k = chk["nested_empty"]
        if obj.get(k) != []: return False, f"{k}={obj.get(k)!r} want []"
    return True, "ok"

def run_struct(host, tier, label):
    print(f"\n=== {label}")
    print(f"    gate: {tier['gate']}")
    ok = trunc = 0
    for it in tier["items"]:
        content, reasoning, fin = ask(host, it["q"], n_predict=tier.get("n_predict", 512))
        obj = extract_json(content) or (extract_json(reasoning) if fin != "length" else None)
        good, why = check_struct(obj, it["check"])
        # A reply that ran out of budget produced no JSON because it never finished, not
        # because the model cannot emit JSON. Dry run 01 scored three of these FAIL and then
        # printed "NOT usable for tool calling" off them.
        truncated = (not good) and fin == "length"
        trunc += truncated
        ok += good
        status = "TRUNCATED" if truncated else ("PASS" if good else "FAIL")
        print(f"    {it['id']}  {status:<18} {why}", flush=True)
        record(tier=label, id=it["id"], status=status, why=why, finish=fin,
               content=content, reasoning=reasoning)
    print(f"    -> {ok}/{len(tier['items'])}" + (f"   ({trunc} truncated -> VOID)" if trunc else ""))
    return ok, len(tier["items"]), trunc

def run_tier(host, tier, label):
    print(f"\n=== {label}: {tier['purpose'][:70]}...")
    print(f"    gate: {tier['gate']}")
    ok = trunc = 0
    for it in tier["items"]:
        content, reasoning, fin = ask(host, it["q"], n_predict=tier.get("n_predict", 512),
                                      prompt=tier.get("prompt"))
        # B2 rule: reasoning is admissible only when the response actually finished
        text = content + ("\n" + reasoning if fin != "length" else "")
        m = ANS.search(text)
        got = m.group(1).strip() if m else ""
        gold = it["gold"]
        if gold == "UNKNOWN":
            # Union with tier_cal's ABSTAIN set. T1-05 gates the whole fixture at 5/5, and
            # its original whitelist misses "I don't know" -> a healthy model would halt the
            # run before tier_cal executed. Widening only: nothing that passed before fails now.
            hit = (abstain_key(got) in ABSTAIN
                   or any(w in norm(got) for w in ("unknown", "doesnotexist", "nosuch",
                                                   "fictional", "notreal", "cannot", "noinfo")))
        else:
            hit = answer_matches(got, gold)
        ok += hit
        trunc += (fin == "length" and not hit)
        status = "PASS" if hit else ("NO-ANSWER" if not got else "FAIL")
        if fin == "length": status += " (truncated)"
        print(f"    {it['id']}  {status:<20} got={got[:34]!r:<38} want={gold!r}", flush=True)
        record(tier=label, id=it["id"], status=status, got=got, gold=gold, finish=fin,
               content=content, reasoning=reasoning)
    print(f"    -> {ok}/{len(tier['items'])}" + (f"   ({trunc} truncated)" if trunc else ""))
    return ok, len(tier["items"]), trunc


def run_cal(host, tier, label):
    """Paired calibration tier. Reports a 2x2 and three rates, never a single score.

    An unanswerable-only set rewards timidity: a model that abstains on everything scores
    100%, and quantisation plausibly makes models MORE timid, so it would report damage as
    improvement. Every item here has an obscurity-matched partner on the other arm, and the
    over-abstention rate is reported next to the confabulation rate for exactly that reason.
    FAILURE_MODES.md AFM-22.
    """
    print(f"\n=== {label}")
    print(f"    {tier['scope'].splitlines()[0][:90]}")
    print(f"    gate: {tier['gate']}")
    tally = {"answerable": collections.Counter(), "unanswerable": collections.Counter()}
    multi = 0
    for it in tier["items"]:
        content, reasoning, fin = ask(host, it["q"], n_predict=tier.get("n_predict", 512),
                                      prompt=tier.get("prompt"))
        got, nmatch = pick_answer(content, reasoning, fin)
        multi += nmatch > 1
        verdict = classify(got, it["gold"])
        if verdict == "NO-ANSWER" and fin == "length":
            verdict = "TRUNCATED"
        tally[it["arm"]][verdict] += 1
        flag = f"  [{nmatch} matches]" if nmatch > 1 else ""
        print(f"    {it['id']}  {it['arm']:<12} {verdict:<17} "
              f"got={got[:30]!r:<34} want={it['gold']!r}{flag}", flush=True)
        record(tier=label, id=it["id"], arm=it["arm"], status=verdict, got=got,
               gold=it["gold"], finish=fin, matches=nmatch,
               content=content, reasoning=reasoning)

    A, U = tally["answerable"], tally["unanswerable"]
    nA, nU = sum(A.values()), sum(U.values())
    print(f"\n    {'':<14}{'CORRECT':>9}{'WRONG':>9}{'ABSTAIN':>9}{'TRUNC':>8}{'NOANS':>8}")
    for arm, c in (("answerable", A), ("unanswerable", U)):
        print(f"    {arm:<14}{c['ANSWERED-CORRECT']:>9}{c['ANSWERED-WRONG']:>9}"
              f"{c['ABSTAINED']:>9}{c['TRUNCATED']:>8}{c['NO-ANSWER']:>8}")

    confab, overabs, acc = U["ANSWERED-WRONG"], A["ABSTAINED"], A["ANSWERED-CORRECT"]
    trunc = A["TRUNCATED"] + U["TRUNCATED"]
    print(f"\n    confabulation   {confab}/{nU}   (answered an unanswerable question)  <-- HEADLINE")
    print(f"    over-abstention {overabs}/{nA}   (refused a question that has an answer)")
    print(f"    accuracy        {acc}/{nA}   (answerable arm, for context)")
    if trunc:
        print(f"    !! {trunc} item(s) TRUNCATED — excluded from the 2x2, and the run is VOID.")
        print(f"       Raise tier_cal.n_predict; do NOT read truncation as a failure to answer.")
    if multi:
        print(f"    !! {multi} item(s) had >1 `Exact Answer:` line — the PARSE is suspect on")
        print(f"       those, not the model. Read the raw replies before believing them.")
    return dict(confab=confab, overabs=overabs, acc=acc, nA=nA, nU=nU, trunc=trunc, multi=multi,
                max_confab=tier.get("gate_confabulation_max", 3),
                max_overabs=tier.get("gate_over_abstention_max", 3))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8080")
    ap.add_argument("--fixture", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                      "fixture_v0_beta.json"))
    ap.add_argument("--tier", choices=["1", "2", "struct", "cal", "both", "all"],
                    default="both")
    ap.add_argument("--only", help="comma-separated item ids; run just these")
    ap.add_argument("--jsonl", help="append per-item results here, flushed as they complete "
                                    "(survives a killed run)")
    ap.add_argument("--effort", choices=["low", "medium", "high", "xhigh"],
                    help="reasoning_effort via chat_template_kwargs; 'medium' curbs overthinking")
    a = ap.parse_args()
    if a.jsonl:
        globals()["JSONL"] = open(a.jsonl, "a", encoding="utf-8")
        print(f"per-item results -> {a.jsonl}")
    if a.effort:
        globals()["EFFORT"] = a.effort
        print(f"reasoning_effort = {a.effort}")
    fx = json.load(open(a.fixture))
    if a.only:
        want = {x.strip() for x in a.only.split(",") if x.strip()}
        for _t in ("tier1", "tier2", "tier_struct", "tier_cal"):
            if _t in fx:
                fx[_t] = dict(fx[_t], items=[i for i in fx[_t]["items"] if i["id"] in want])
        print(f"--only: {sorted(want)}")
    res = {}
    if a.tier in ("1", "both", "all"): res["t1"] = run_tier(a.host, fx["tier1"], "TIER 1 (plumbing)")
    if a.tier in ("2", "both", "all"): res["t2"] = run_tier(a.host, fx["tier2"], "TIER 2 (model sanity)")
    if a.tier in ("struct", "all") and "tier_struct" in fx:
        res["ts"] = run_struct(a.host, fx["tier_struct"], "TIER STRUCT (tool calling / JSON)")
    if a.tier in ("cal", "all") and "tier_cal" in fx:
        res["cal"] = run_cal(a.host, fx["tier_cal"], "TIER CAL (calibration / abstention)")
    print("\n" + "="*70)
    if "t1" in res:
        o, n, tr = res["t1"]
        # A truncated plumbing item is a BUDGET failure. Dry run 01 printed "STACK IS BROKEN"
        # because T1-05 — the abstention item, the most expensive item in the fixture — ran
        # out of tokens on a perfectly healthy stack.
        v = "PASS" if o == n else ("BUDGET" if tr and o + tr == n else "FAIL")
        tail = {"PASS": "", "BUDGET": f"   <-- {tr} item(s) TRUNCATED; raise tier1.n_predict, "
                                      "the stack is NOT implicated",
                "FAIL": "   <-- STACK IS BROKEN, stop here"}[v]
        print(f"TIER 1 {v}  ({o}/{n}, gate {n}/{n}){tail}")
    if "t2" in res:
        o, n, tr = res["t2"]
        # Truncation makes the score a floor: PASSING despite it is still a pass, but
        # FAILING with items that never finished is inconclusive, not a model result.
        v = "PASS" if o >= 6 else ("INCONCLUSIVE" if tr else "FAIL")
        print(f"TIER 2 {v}  ({o}/{n}, gate >=6/{n})"
              + (f"   [{tr} truncated — score is a FLOOR]" if tr else ""))
    if "ts" in res:
        o, n, tr = res["ts"]
        v = "VOID (truncation)" if tr else ("PASS" if o >= 5 else "FAIL")
        print(f"TIER STRUCT {v}  ({o}/{n}, gate >=5/{n})")
        if tr:
            print(f"  {tr} item(s) never finished. No claim about tool calling is supported"
                  "\n  by this run — raise tier_struct.n_predict and re-run.")
        elif "t2" in res and res["t2"][0] >= 6 and o < 5:
            print("  NOTE: tiers 1-2 pass but structured output fails — this quant is usable"
                  "\n        for chat and NOT usable for tool calling. That is a real result,"
                  "\n        not a fixture bug.")

    if "cal" in res:
        c = res["cal"]
        ok = (c["confab"] <= c["max_confab"] and c["overabs"] <= c["max_overabs"]
              and c["trunc"] == 0)
        verdict = "VOID (truncation)" if c["trunc"] else ("PASS" if ok else "FAIL")
        print(f"TIER CAL {verdict}  (confab {c['confab']}/{c['nU']}, "
              f"over-abstain {c['overabs']}/{c['nA']}, "
              f"gate <={c['max_confab']} and <={c['max_overabs']})")
        if c["trunc"]:
            print("  Rates above are meaningless on a VOID run — they count only the items"
                  "\n  that finished. Fix the budget and re-run; do not read them.")
        else:
                print("  Confabulation here is a FLOOR: the parser prefers the last answer line and"
              "\n  the abstention match is permissive, so borderline replies land as ABSTAINED."
                  "\n  Error runs toward under-reporting confabulation, never over.")
        if c["confab"] == 0 and c["overabs"] >= 6:
            print("  NOTE: zero confabulation with heavy over-abstention is NOT good calibration."
                  "\n        A model that refuses everything scores perfectly on the unanswerable"
                  "\n        arm. That is the failure this tier's paired design exists to catch.")
        if "t2" in res and res["t2"][0] >= 6 and not ok and c["trunc"] == 0:
            print("  NOTE: tiers 1-2 pass but calibration fails — this quant answers questions"
                  "\n        correctly and no longer knows which ones it cannot answer. No"
                  "\n        accuracy metric in this project would have surfaced that.")
