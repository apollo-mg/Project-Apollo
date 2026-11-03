#!/usr/bin/env python3
"""Abstend pipeline, last step: a RESULT draft from committed files only, so a human writes the interpretation on top of
facts that were copied, not retyped (2026-11-02: three hand-written RESULTs so far, each one retyping the same lines).

  write_result.py RECIPE [--stdout]      (also: abstend.py result RECIPE)

Reads the recipe, PREREG_<model_id>.md, state.log (every launch of the chain) and scorecard.csv; writes
data/receipts/abstend/<model_id>/RESULT_<model_id>.draft.md. Never reads raw/ (gitignored, absent in the cloud), never
writes interpretation, never touches a hand-written RESULT_<model_id>.md, and says what is missing instead of failing.
Stdlib only: it runs in the cloud, where the project venv does not exist."""
import argparse, csv, datetime, hashlib, json, re, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
TS = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) (.*)$")
# the chain's own words (abstend.py HEAD/LOCAL/SSH/MODE/ABENCH); a gate line is quoted, never paraphrased
GATE = re.compile(r"^guard |launch guard|sha256 ok|sha256 mismatch|staged, sha256|smoke (OK|FAILED)|SMOKE FAILED|^defaults audit|"
                  r"verified against its frozen question hashes|server sampler defaults")
HOSTL = re.compile(r": kernel |MemAvailable|clef (paused|restored)|^restored:|host powered|clocks ")
STAGE = re.compile(r"\brc=|^verdicts_\S+\.csv:")
DEV = re.compile(r"ABORT|SKIPPED|FAILED|did not exit|\brc=(?!0\b)\S+")
MISSING = "**Missing:**"


def rel(p, root): return str(Path(p).resolve().relative_to(Path(root).resolve()))


def git(root, *a):
    r = subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def committed(p, root):
    """'commit `abc12345`', or why the file is not a committed fact. The draft reads the working tree; this says whether
    that is what was committed."""
    r = rel(p, root); hs = (git(root, "log", "--abbrev=8", "--format=%h", "--", r) or "").split()
    if not hs: return "not committed"
    # the RESULTs cite the commit that registered a file; later commits are appended deviations. A shallow clone (the
    # cloud) stops at its graft, so there the oldest hash is the graft, not the registration.
    return f"added `{hs[-1]}`" + (f", last changed `{hs[0]}`" if len(hs) > 1 else "") + (", **modified since**" if git(root, "status", "--porcelain", "--", r) else "")


def launches(lines):
    """state.log -> one list of lines per 'chain start' (a refused or aborted launch is followed by a relaunch in the same
    log: Phi-4-mini, 2026-10-28). Lines before the first start, if any, form a launch of their own."""
    out = []
    for l in lines:
        m = TS.match(l)
        if m and m.group(3) == "chain start" or not out: out.append([])
        out[-1].append(l)
    return out


def span(run):
    ts = [(m.group(1), m.group(2), m.group(3)) for m in map(TS.match, run) if m]
    if not ts: return "no timestamped lines"
    (d0, t0, _), done = ts[0], next(((d, t) for d, t, x in reversed(ts) if x == "DONE"), None)   # the last DONE: a relaunch ends later
    end, why = (done, "DONE") if done else (ts[-1][:2], "last timestamped line; **no DONE line**")
    return f"{d0} {t0} to " + (end[1] if end[0] == d0 else f"{end[0]} {end[1]}") + f" ({why})"


def quote(lines): return [f"    {l}" for l in lines]


def fmt(v): return v if v not in (None, "") else "-"


def card_table(rows):
    out = ["| metric | value | 95 % (Wilson) | n |", "|---|---|---|---|"]
    out += [f"| {r['metric']} | {fmt(r['value'])} | [{fmt(r['ci_lo'])}, {fmt(r['ci_hi'])}] | {fmt(r['n'])} |" for r in sorted(rows, key=lambda r: r["metric"])]
    return out


def draft(recipe, root=ROOT, today=None):
    root = Path(root); recipe = Path(recipe); out = []
    try:
        rc = json.loads(recipe.read_text())
    except (OSError, ValueError) as e:
        raise SystemExit(f"cannot read the recipe {recipe}: {e}")
    mid = rc.get("model_id") or recipe.stem; d = root / "data" / "receipts" / "abstend" / mid
    m, f, e = rc.get("model", {}), rc.get("file", {}), rc.get("engine", {}); modes = rc.get("modes", {})
    rhash = hashlib.sha256(recipe.read_bytes()).hexdigest()
    rrel = rel(recipe, root) if recipe.resolve().is_relative_to(root.resolve()) else recipe.name
    out += [f"# RESULT (draft): {m.get('display', mid)} {f.get('quant', '')}: Abstend standard card".replace("  ", " "), "",
            f"_Draft written by `data/scorecard/write_result.py` on {today or datetime.date.today().isoformat()} from committed files. "
            f"Facts and numbers only: check them, write the interpretation, and save as `RESULT_{mid}.md`._", ""]

    # header lines, in the order the hand-written RESULTs use: prereg, recipe, chain, run
    pp = d / f"PREREG_{mid}.md"; head = []
    if pp.exists():
        pt = pp.read_text(); reg = re.search(r"Registered (\d{4}-\d{2}-\d{2})", pt); named = re.search(r"sha256:([0-9a-f]{64})", pt)
        nm = ("names no recipe hash" if not named else f"names recipe sha256 `{named.group(1)[:8]}...`, "
              + ("which matches the recipe" if named.group(1) == rhash else "**which does not match the recipe**"))
        head.append(f"**Prereg:** `PREREG_{mid}.md` ({committed(pp, root)}; registered {reg.group(1) if reg else '**no registered date found**'}; {nm}).")
        later = [h[3:] for h in pt.splitlines() if re.match(r"## (Deviation|Addendum)", h)]
    else:
        head.append(f"{MISSING} `PREREG_{mid}.md` is not in `{rel(d, root) if d.exists() else 'data/receipts/abstend/' + mid}`."); later = []
    head.append(f"**Recipe:** `{rrel}` (sha256 `{rhash[:8]}...`; {committed(recipe, root)}).")
    chains = sorted(d.glob("chain_*.sh")) if d.exists() else []
    head.append("**Chain:** " + (", ".join(f"`{c.name}` ({committed(c, root)})" for c in chains) + "." if chains else f"{MISSING} no `chain_*.sh`."))
    sl = d / "state.log"; runs = launches(sl.read_text().splitlines()) if sl.exists() else []
    head.append(f"**Run:** {len(runs)} launch{'es' if len(runs) != 1 else ''} in `state.log`, {span([l for r in runs for l in r])}." if runs
                else f"**Run:** {MISSING} `state.log`.")
    head.append(f"**Model:** `{f.get('repo', '?')}` rev `{f.get('revision', '?')}`, `{f.get('name', '?')}` (sha256 `{f.get('sha256', '?')[:8]}...`). "
                f"**Host:** {rc.get('host', '?')}. **Engine:** {e.get('name', '?')} `{e.get('commit', '?')}` `{e.get('build', '?')}`, `{e.get('flags', '?')}`.")
    out += [" ".join(head[:2]), " ".join(head[2:4]), head[4], ""]
    if later: out += ["Appended to the prereg after registration:"] + [f"- {h}" for h in later] + [""]

    # the run, as state.log recorded it
    devs = []; out += ["## Run", ""]
    if not sl.exists():
        out += [f"{MISSING} `{mid}/state.log`. Chain times, gate lines, host state and deviations cannot be reported.", ""]
    else:
        out += [f"`state.log` ({committed(sl, root)}): {len(runs)} launch{'es' if len(runs) != 1 else ''}.", ""]
        for i, run in enumerate(runs, 1):
            gate = [l for l in run if GATE.search(l)]; host = [l for l in run if HOSTL.search(l)]; stage = [l for l in run if STAGE.search(l)]
            devs += [(i, l) for l in run if DEV.search(l)]
            out += [f"**Launch {i}:** {span(run)}.", ""]
            for name, ls in (("Gates", gate), ("Host", host), ("Stages", stage)):
                out += [f"{name}:", ""] + (quote(ls) if ls else ["    (none recorded)"]) + [""]
        if not any("kernel" in l for r in runs for l in r):
            out += ["No kernel or firmware line: chains log host state from 2026-10-29 (`RESULT_llama-3.1-8b-instruct.md`).", ""]

    out += ["## Deviations", ""]
    if not sl.exists(): out += ["Not known: `state.log` is missing.", ""]
    elif not devs: out += ["None in `state.log`: no `ABORT`, `SKIPPED` or `FAILED` line, and every `rc=` is 0.", ""]
    else: out += ["Every `ABORT`, `SKIPPED`, `FAILED` and non-zero `rc=` line in `state.log`, verbatim:", ""] + quote(f"[launch {i}] {l}" for i, l in devs) + [""]

    # the card, as build_scorecard.py wrote it
    sc = root / "data" / "scorecard" / "scorecard.csv"; out += ["## Card", ""]
    if not sc.exists():
        out += [f"{MISSING} `data/scorecard/scorecard.csv`.", ""]; rows = []
    else:
        with open(sc, newline="") as fh: rows = [r for r in csv.DictReader(fh) if r.get("model_id") == mid]
        out += [f"From `data/scorecard/scorecard.csv` ({committed(sc, root)}), Wilson 95 % intervals as `build_scorecard.py` wrote them.", ""]
    if sc.exists():
        for mode, mm in modes.items():
            arm = mm.get("arm", "?"); rs = [r for r in rows if r["config_id"] == f"m1:{arm}"]
            first = rs[0] if rs else {}
            out += [f"### {mode} (arm `{arm}`{', primary' if mm.get('primary') else ''})", ""]
            if not rs: out += [f"{MISSING} no `m1:{arm}` rows for `{mid}` in `scorecard.csv`.", ""]; continue
            out += [f"Instrument {first['instrument']}; thinking {first['thinking']}; decoding {first['decoding']}; receipt `{first['receipt']}`.", ""] + card_table(rs) + [""]
        ab = (rc.get("abench") or {}).get("arm"); ins = next((i for i in rc.get("instruments", []) if i.startswith("AbstentionBench-")), None)
        if ab or ins:
            rs = [r for r in rows if r["config_id"] == f"abench:{ab}"]
            out += [f"### AbstentionBench (arm `{ab or '?'}`)", ""]
            if not rs: out += [f"{MISSING} no `abench:{ab or '?'}` rows for `{mid}` in `scorecard.csv` (recipe instrument {ins or 'not named'}).", ""]
            else:
                names = sorted({r["instrument"] for r in rs})
                out += [f"Instrument {', '.join(names)}" + ("" if names == [ins] else f" (the recipe names {ins or 'none'})")
                        + f"; thinking {rs[0]['thinking']}; decoding {rs[0]['decoding']}; receipt `{rs[0]['receipt']}`.", ""] + card_table(rs) + [""]
        other = sorted({r["config_id"] for r in rows} - {f"m1:{mm.get('arm')}" for mm in modes.values()} - {f"abench:{(rc.get('abench') or {}).get('arm')}"})
        if other: out += ["Other rows for this model in `scorecard.csv`, not from this recipe: " + ", ".join(f"`{c}`" for c in other) + ".", ""]

    out += ["## Interpretation", "", "_To be written by a human. This draft states facts and numbers only._", ""]
    return "\n".join(out)


def write(recipe, root=ROOT, stdout=False, today=None):
    """Write the draft next to the prereg. Refuses when a hand-written RESULT_<model_id>.md exists: a draft beside a
    finished RESULT invites the wrong one being read (--stdout still renders it)."""
    root = Path(root); txt = draft(recipe, root, today)
    if stdout: print(txt); return None
    mid = json.loads(Path(recipe).read_text()).get("model_id") or Path(recipe).stem; d = root / "data" / "receipts" / "abstend" / mid
    final, out = d / f"RESULT_{mid}.md", d / f"RESULT_{mid}.draft.md"
    if final.exists(): raise SystemExit(f"refused: {rel(final, root)} exists (hand-written); nothing written. --stdout renders the draft.")
    if "/home/" in txt: print("warning: the draft contains a /home/ path; remove it before committing (public repo)", file=sys.stderr)
    d.mkdir(parents=True, exist_ok=True); out.write_text(txt); print("wrote", rel(out, root)); return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recipe"); ap.add_argument("--stdout", action="store_true", help="render the draft without writing it")
    a = ap.parse_args(); write(a.recipe, stdout=a.stdout)


if __name__ == "__main__":
    main()
