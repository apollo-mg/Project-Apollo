#!/usr/bin/env python3
"""Score PREREG_HEMM_TECHWRITING.md. Needs tasks_private.json (ledger windows) locally."""
import json, math, re, sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import ledger_build as lb                # noqa: E402
from ledger_validate import classify     # noqa: E402

TASKS = {t["id"]: t for t in json.load(open(HERE / "tasks_private.json"))["tasks"]}
ARMS = ("S5", "H5", "S6")


def load(arm):
    out = {}
    for f in (HERE / "raw" / f"{arm}.jsonl", HERE / "raw" / f"{arm}_ledger.jsonl"):
        for l in open(f):
            r = json.loads(l); out[r["id"]] = r
    return out


R = {a: load(a) for a in ARMS}
NUM = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(?:%|x)?(?![\w])")


def norm_nums(text, answer=False):
    out = set()
    for line in text.split("\n"):
        if answer:
            line = re.sub(r"^\s*(\d+[.)]\s)", " ", line)          # list ordinals at line start
        for m in NUM.finditer(line):
            v = m.group(1).replace(",", "").rstrip(".")
            if not v:
                continue
            if answer and re.fullmatch(r"\d", v):                  # lone single digits
                continue
            if answer and re.fullmatch(r"20\d\d", v):              # years
                continue
            out.add(v)
    return out


def invented_numbers(t, content):
    src = t.get("source") or ""
    return sorted(norm_nums(content, True) - norm_nums(src + " " + t["user_prompt"]))


def invented_idents(t, content):
    src = (t.get("source") or "") + " " + t["user_prompt"]
    ids = set(re.findall(r"`([^`\n]{2,80})`", content))
    return sorted(i for i in ids if i not in src)


def sign_test(w, l):
    n = w + l
    if n == 0: return 1.0
    k = min(w, l)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


res = {"per_arm": {}, "preference": {}, "ledger": {}}
for a in ARMS:
    inv_n, inv_i, facts, mis, words, reason, strike, fin = 0, 0, 0, 0, 0, 0, 0, {}
    detail = {}
    for tid, t in TASKS.items():
        r = R[a][tid]; c = r.get("content") or ""
        fin[r.get("finish_reason")] = fin.get(r.get("finish_reason"), 0) + 1
        if t["kind"] == "ledger":
            continue
        words += len(c.split()); reason += len(r.get("reasoning") or "")
        strike += len(re.findall(r"~~[^~\n]+~~", c))
        d = {}
        if t["kind"] in ("summary", "bug_report", "clarity"):
            d["inv_num"] = invented_numbers(t, c); inv_n += len(d["inv_num"])
        if t["kind"] in ("bug_report", "docs"):
            d["inv_id"] = invented_idents(t, c); inv_i += len(d["inv_id"])
        if t["kind"] == "explain":
            d["facts"] = sum(bool(re.search(p, c)) for p in t["key_facts"])
            d["mis"] = sum(bool(re.search(p, c)) for p in t["misconceptions"])
            facts += d["facts"]; mis += d["mis"]
        detail[tid] = d
    lg = {}
    for tid, t in TASKS.items():
        if t["kind"] != "ledger":
            continue
        c = R[a][tid].get("content") or ""
        ev = [tuple(x) for x in t["events"]]
        _, tags = lb.annotate_unverified(c, ev)
        lg[tid] = {"unverified_tags": tags, "classify": classify(c) or "ok",
                   "bad_headings": len(re.findall(r"^#{1,2}\s", c, re.M)), "words": len(c.split())}
    res["per_arm"][a] = {"invented_numbers": inv_n, "invented_identifiers": inv_i, "explain_key_facts": facts,
                         "explain_misconceptions": mis, "words_total_20": words, "reasoning_chars_20": reason,
                         "strikethrough_spans": strike, "finish": fin, "detail": detail}
    res["ledger"][a] = lg

# blind preference S5 vs H5
mapping = json.load(open(HERE / "raw" / "ab_mapping.json"))
ratings = json.load(open(HERE / "raw" / "ratings.json"))
h_win = s_win = tie = 0; guess_right = guess_wrong = unsure = 0
rows = []
for tid, m in mapping.items():
    rt = ratings.get(tid, {}); p, g = rt.get("pref"), rt.get("guess")
    winner = "tie" if p == "tie" else (m[p] if p in ("A", "B") else None)
    if winner == "H5": h_win += 1
    elif winner == "S5": s_win += 1
    elif winner == "tie": tie += 1
    gok = None if g not in ("A", "B") else (m[g] == "H5")
    if gok is True: guess_right += 1
    elif gok is False: guess_wrong += 1
    else: unsure += 1
    lh = len((R["H5"][tid].get("content") or "")); ls = len((R["S5"][tid].get("content") or ""))
    rows.append({"id": tid, "winner": winner, "guess_correct": gok, "h5_chars": lh, "s5_chars": ls,
                 "winner_longer": None if winner not in ("H5", "S5") else
                 ((lh > ls) if winner == "H5" else (ls > lh))})
dec = [r for r in rows if r["winner"] in ("H5", "S5")]
res["preference"] = {"H5_wins": h_win, "S5_wins": s_win, "ties": tie, "sign_test_p": sign_test(h_win, s_win),
                     "guess_right": guess_right, "guess_wrong": guess_wrong, "guess_unsure": unsure,
                     "guess_sign_p_vs_chance": sign_test(guess_right, guess_wrong),
                     "longer_draft_won": sum(r["winner_longer"] for r in dec), "decided": len(dec),
                     "H5_wins_when_guess_right": sum(1 for r in dec if r["guess_correct"] and r["winner"] == "H5"),
                     "S5_wins_when_guess_right": sum(1 for r in dec if r["guess_correct"] and r["winner"] == "S5"),
                     "H5_wins_when_guess_wrong_or_unsure": sum(1 for r in dec if not r["guess_correct"] and r["winner"] == "H5"),
                     "S5_wins_when_guess_wrong_or_unsure": sum(1 for r in dec if not r["guess_correct"] and r["winner"] == "S5"),
                     "rows": rows}
json.dump(res, open(HERE / "RESULT_techwriting.json", "w"), indent=1)
P = res["preference"]
print(f"PREFERENCE  H5 {P['H5_wins']}  S5 {P['S5_wins']}  tie {P['ties']}   sign p={P['sign_test_p']:.3f}")
print(f"GUESS       right {P['guess_right']}  wrong {P['guess_wrong']}  unsure {P['guess_unsure']}  p vs chance={P['guess_sign_p_vs_chance']:.3f}")
print(f"LENGTH      longer draft won {P['longer_draft_won']}/{P['decided']} decided")
print(f"SPLIT       guess right: H5 {P['H5_wins_when_guess_right']} S5 {P['S5_wins_when_guess_right']} | guess wrong/unsure: H5 {P['H5_wins_when_guess_wrong_or_unsure']} S5 {P['S5_wins_when_guess_wrong_or_unsure']}")
for a in ARMS:
    s = res["per_arm"][a]
    print(f"{a}: inv_num {s['invented_numbers']:2d} inv_id {s['invented_identifiers']:2d} facts {s['explain_key_facts']:2d}/20 "
          f"mis {s['explain_misconceptions']} words {s['words_total_20']} reasoning {s['reasoning_chars_20']} "
          f"strike {s['strikethrough_spans']} finish {s['finish']}")
    print("    ledger:", {k: (v["unverified_tags"], v["classify"], v["bad_headings"], v["words"]) for k, v in res["ledger"][a].items()})
