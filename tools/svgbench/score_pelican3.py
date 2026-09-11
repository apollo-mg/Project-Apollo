#!/usr/bin/env python3
"""Score data/receipts/svgbench-pelican3 against PREREG_PELICAN3.md: rules R1-R5, predictions P-P1..P-P6.

Written and committed before any BASE or QWOPUS data existed. The P-P6 judgment ("failing only on
the artifact types in RUN_NOTES.md") is made in the receipt; this script only prints each
drawing's failing checks.
"""
import itertools, json, re, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/svgbench"))
import run_ladder as R  # noqa: E402  -- probe() re-scores an R2 re-extraction with the same scorer

OUT = ROOT / "data/receipts/svgbench-pelican3"
OLD = ROOT / "data/receipts/svgbench-davidau/results.jsonl"
ARMS = ["BASE", "QWOPUS", "DAVIDAU"]
REPS = range(1, 6)
INF = float("inf")


def load():
    p1, meta, incidents = {}, {}, []
    for line in open(OUT / "results.jsonl"):
        if not line.strip():
            continue
        r = json.loads(line)
        k = (r.get("quant"), r.get("rep"))
        if r.get("step") == "p1":
            p1[k] = r                  # the last record for a rep wins
        elif r.get("step") == "meta":
            meta[k] = r
        else:
            incidents.append(r)
    return p1, meta, incidents


def mw_less(a, b):
    """Exact one-sided Mann-Whitney for 'a tends lower than b': P(U <= U_obs) over all relabelings."""
    def u(x, y):
        return sum((xi > yi) + 0.5 * (xi == yi) for xi in x for yi in y)
    obs, pool, hits, tot = u(a, b), a + b, 0, 0
    for idx in itertools.combinations(range(len(pool)), len(a)):
        s = set(idx)
        hits += u([pool[i] for i in idx], [pool[i] for i in range(len(pool)) if i not in s]) <= obs + 1e-9
        tot += 1
    return obs, hits / tot


def capped(r):                         # R1
    e = (r.get("error") or "").lower()
    return "timed out" in e or "timeout" in e or "backstop" in e


def think(arm, rep, r):
    """R2. Returns (thinking chars, answer chars, how, rescore)."""
    f = OUT / f"{arm}_r{rep}_p1.content.txt"
    content = f.read_text() if f.exists() else ""
    if r.get("reasoning_chars"):
        return r["reasoning_chars"], len(content), "parsed", None
    if "</think>" in content:
        head, tail = content.rsplit("</think>", 1)
        th = head.split("<think>", 1)[-1]
        svgs = re.findall(r"<svg.*?</svg>", tail, re.S | re.I)
        rescore = None
        if svgs:
            b = str(OUT / f"{arm}_r{rep}_p1_R2")
            Path(b + ".svg").write_text(svgs[-1])
            pr = R.probe(b + ".svg", b + ".png")
            rescore = (pr.get("score"), pr.get("max"))
        return len(th), len(tail), "R2 re-extracted", rescore
    return 0, len(content), "no thinking", None


def failing(checks):
    if isinstance(checks, dict):
        return [k for k, v in checks.items() if not v]
    return checks or []


def contact_sheet(rows):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("PIL not available; no contact sheet")
        return
    tw, th, pad, lab = 320, 240, 12, 34
    sheet = Image.new("RGB", (pad + 5 * (tw + pad), pad + 3 * (th + lab + pad)), "white")
    d = ImageDraw.Draw(sheet)
    for i, arm in enumerate(ARMS):
        for j, rep in enumerate(REPS):
            x, y = pad + j * (tw + pad), pad + i * (th + lab + pad)
            row = rows.get((arm, rep))
            png = None
            if row:
                for cand in (OUT / f"{arm}_r{rep}_p1_R2.png", OUT / f"{arm}_r{rep}_p1.png"):
                    if cand.exists():
                        png = cand
                        break
            if png:
                im = Image.open(png).convert("RGB")
                im.thumbnail((tw, th))
                sheet.paste(im, (x + (tw - im.width) // 2, y + lab + (th - im.height) // 2))
            d.rectangle([x, y + lab, x + tw, y + lab + th], outline=(200, 200, 200))
            txt = f"{arm} r{rep}"
            if row:
                txt += f"  {row['tok_s']} tok  score {row['score']}"
            d.text((x + 4, y + 8), txt, fill=(20, 20, 20))
    sheet.save(OUT / "contact_sheet.png")
    print(f"contact sheet: {OUT / 'contact_sheet.png'}")


def main():
    p1, meta, incidents = load()
    print("== integrity (R3-R5)")
    for arm in ARMS:
        shas = {meta[(arm, rep)].get("prompt_sha256") for rep in REPS if (arm, rep) in meta}
        tails = {meta[(arm, rep)].get("prompt_tail") for rep in REPS if (arm, rep) in meta}
        kvs = [meta[(arm, rep)].get("kv_bpv") for rep in REPS if (arm, rep) in meta]
        print(f"   {arm:8s} prompt hashes {len(shas)} distinct {sorted(str(s)[:12] for s in shas)} | tail {tails} | kv_bpv {kvs}")
    for r in incidents:
        print(f"   incident: {r.get('quant')} r{r.get('rep')} {r.get('step')}: {r.get('error')}")

    rows = {}
    print("\n== per drawing")
    print(f"   {'arm':8s} rep  tokens  think_ch  answer_ch  score   finish  elapsed  how / failing checks")
    for arm in ARMS:
        for rep in REPS:
            r = p1.get((arm, rep))
            if r is None:
                print(f"   {arm:8s} r{rep}  (missing)")
                continue
            if capped(r):
                rows[(arm, rep)] = dict(tok=INF, tok_s="CAPPED", think=None, ans=None, score="-", how="R1 capped")
                print(f"   {arm:8s} r{rep}  CAPPED ({r.get('error')})")
                continue
            if r.get("error"):
                print(f"   {arm:8s} r{rep}  ERROR {r.get('error')}")
                continue
            th, an, how, rescore = think(arm, rep, r)
            score = f"{r.get('score')}/{r.get('max')}" if rescore is None else f"{rescore[0]}/{rescore[1]} (R2)"
            rows[(arm, rep)] = dict(tok=r["tokens"], tok_s=r["tokens"], think=th if how != "no thinking" else None,
                                    ans=an, score=score, how=how)
            print(f"   {arm:8s} r{rep}  {r['tokens']:6d}  {th:8d}  {an:9d}  {score:7s} {str(r.get('finish')):7s} "
                  f"{r.get('elapsed_s'):6.0f}s  {how} {failing(r.get('checks'))}")

    def col(arm, key):
        return [rows[(arm, rep)][key] for rep in REPS if (arm, rep) in rows and rows[(arm, rep)][key] is not None]

    print("\n== medians (capped = above every completed rep)")
    for arm in ARMS:
        t, k, a = col(arm, "tok"), col(arm, "think"), col(arm, "ans")
        fmt = lambda v: "-" if not v else f"{statistics.median(v):,.0f} [{min(v):,.0f}-{max(v):,.0f}]"
        print(f"   {arm:8s} n={len(t)} tokens {fmt(t)} | thinking chars {fmt(k)} | answer chars {fmt(a)}")

    print("\n== predictions")
    d, b, q = col("DAVIDAU", "think"), col("BASE", "think"), None
    u, p = mw_less(d, b) if d and b else (None, None)
    print(f"   P-P1 DAVIDAU thinking < BASE: U = {u}, exact one-sided p = {p}  -> "
          f"{'CONFIRMED' if p is not None and p < 0.05 else 'not confirmed'}")
    d, b = col("DAVIDAU", "tok"), col("BASE", "tok")
    u, p = mw_less(d, b) if d and b else (None, None)
    print(f"   P-P2 DAVIDAU tokens < BASE:   U = {u}, exact one-sided p = {p}  -> "
          f"{'CONFIRMED' if p is not None and p < 0.05 else 'not confirmed'}")
    q, b = col("QWOPUS", "tok"), col("BASE", "tok")
    if q and b:
        mq, mb = statistics.median(q), statistics.median(b)
        print(f"   P-P3 QWOPUS median tokens {mq:,.0f} >= BASE median {mb:,.0f}  -> {'CONFIRMED' if mq >= mb else 'FALSIFIED'}")
    opened = [rows[("QWOPUS", rep)]["how"] for rep in REPS if ("QWOPUS", rep) in rows]
    print(f"   P-P4 QWOPUS opened thinking: {sum(h != 'no thinking' for h in opened)}/{len(opened)} {opened}")
    ncap = sum(1 for v in rows.values() if v["how"] == "R1 capped")
    print(f"   P-P5 capped reps: {ncap}  -> {'CONFIRMED' if ncap == 0 else 'FALSIFIED'}")
    print("   P-P6 judged in the receipt from the failing checks above")

    if OLD.exists():
        old = [json.loads(l) for l in open(OLD) if l.strip()]
        old = [r for r in old if r.get("step") == "p1" and r.get("tokens")]
        print("\n== replication: the three earlier DAVIDAU reps (not pooled)")
        print(f"   tokens {[r['tokens'] for r in old]} | thinking chars {[r.get('reasoning_chars') for r in old]}")
    contact_sheet(rows)


if __name__ == "__main__":
    main()
