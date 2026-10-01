#!/usr/bin/env python3
"""Nightly daydream, stage 3: the model pass and the morning brief.

Two kinds of model call, both on the .73 wake proxy (Qwen3.8-27B; the ledger's known-good endpoint):
1. ADJUDICATE (thinking off, short JSON): for each thread or BACKLOG item with closure candidates from stage 2,
   is it closed, partly closed, or still open? Closed threads are marked closed in the state file, with evidence.
2. PICK (reasoning_effort medium): from the threads still open, choose up to 5 worth picking up next, each with why
   and the cheapest next step. Picks must name real thread ids; anything else is dropped.

Everything else in the brief is mechanical: the proposed BACKLOG edits, recurring failure modes from ledger_retro
(signatures seen in the last 7 days), and counts. If the endpoint fails, the brief is still written without the
model sections and says so (status "degraded").

Writes data/dev_diaries/morning/<date>.md and prints one status line (json) for the runner's heartbeat.
Usage: daydream_brief.py [--host http://127.0.0.1:8099] [--max-adjudicate 60]
"""
import argparse, datetime, json, re, subprocess, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ledger_build import strip_reasoning  # noqa: E402  (the ledger's tested call + think stripping)

MORNING = ROOT / "data" / "dev_diaries" / "morning"


def quick(host, prompt, max_tokens=220, timeout=600):
    body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False}}
    r = urllib.request.Request(host.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        d = json.loads(f.read())
    return strip_reasoning(d["choices"][0]["message"].get("content") or "")


def think(host, prompt, max_tokens=14000, timeout=2400):
    """reasoning_effort medium with a budget big enough to finish thinking (6,144 was not, on the picks prompt)."""
    body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.4,
            "chat_template_kwargs": {"reasoning_effort": "medium"}}
    r = urllib.request.Request(host.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        ch = json.loads(f.read())["choices"][0]
    raw = ch["message"].get("content") or ""
    if ch.get("finish_reason") == "length" and "</think>" not in raw:
        raise RuntimeError("picks hit the token limit before answering (all reasoning)")
    return strip_reasoning(raw)


def last_json(text, kind="{"):
    """The last JSON object (or array) in a completion."""
    close = "}" if kind == "{" else "]"
    for m in reversed([m.start() for m in re.finditer(re.escape(kind), text)]):
        j = text.rfind(close)
        try:
            return json.loads(text[m:j + 1])
        except Exception:
            continue
    return None


ADJ = """You are checking whether an open item from an engineering log has been resolved by LATER work.

Open item (from {src}, {date}):
<<{text}>>

Later evidence (from further down the same file, commit messages, and other files in this project):
{evidence}

Say "closed" only if a snippet addresses THIS item's specific question or quantity and answers it (a fix verified,
a measurement taken, or a decision recorded that retires or shelves it). Evidence about a different aspect of the same
system is NOT closure: e.g. "the server survived" does not close "the store grew too large". "partly" if part of it is
answered and part still stands. When in doubt, "open".
Answer with one line of JSON only: {{"status": "closed" | "partly" | "open", "evidence": <number or null>, "why": "<one short sentence>"}}"""

PICK = """You are the night-shift reviewer for a solo hardware-empirics lab (local LLM inference on Pascal P100s and an RX 9070;
results published as receipts). Below are OPEN threads harvested from the last few days of the lab's diary and receipts,
each with an id, where it came from, how many times it was mentioned, and related earlier work.

Pick up to 5 that are most worth picking up next. Prefer: things that block a claim or a daily-driver feature, cheap
tests that would settle an open question, and threads whose prerequisite has since been met. Skip pure caveats about
scope ("one model", "thinking off"), and work the diary says was shelved. For each pick give the cheapest concrete next
step, not a plan. DO NOT invent commands, flags, script names, file paths or commit ids: use only names that appear
verbatim in the thread or its related text, and otherwise describe the step in plain words. Diary lines can be stale;
if a related line says something was fixed or shelved, do not pick it.

THREADS:
{threads}

Reply with a JSON array only:
[{{"id": "<thread id>", "title": "<5-9 words>", "why": "<1-2 sentences>", "next": "<one concrete step>"}}]"""


def fmt_evidence(ev):
    return "\n".join(f"{n}. [{e['date']} {e['source']}] {e['snippet'][:300]}" for n, e in enumerate(ev, 1))


def retro_recent(days=7):
    out = subprocess.run([str(ROOT / "venv_cachyos/bin/python3"), str(ROOT / "tools/ledger_retro.py"),
                          str(ROOT / "data/dev_diaries")], capture_output=True, text=True).stdout
    cut = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    rows = []
    for l in out.splitlines():
        m = re.search(r"^\s+(.+?)\s+(\d+) parts .*first (\S+)\s+last (\S+)", l)
        if m and m.group(4) >= cut:
            rows.append(f"- **{m.group(1)}**: {m.group(2)} diary parts overall, first {m.group(3)}, last {m.group(4)}")
    return rows


def _norm(t):
    return re.sub(r"[^a-z0-9 ]+", " ", t.lower())[:300].split()


def near_dup(a, b, cut=0.6):
    """Token-set overlap of the first ~300 chars. Catches a sentence edited in place (a new thread id, same claim)."""
    x, y = set(_norm(a)), set(_norm(b))
    return bool(x and y) and len(x & y) / min(len(x), len(y)) >= cut


def shadowed(item, threads, resolved):
    """True when a resolved thread (closed tonight, closed on an earlier night, or suggested) shares a source location
    with item or says nearly the same thing. `threads` must cover EVERY thread in the state file, not only tonight's:
    on 10-01 the open older wording of RESULT_CALIB.md:204 was picked because its closed sibling (closed 09-30) is no
    longer in tonight's links, so a tonight-only resolved set could not see it."""
    if item.get("thread") in resolved:
        return True
    locs = {s for k in resolved for s in threads[k]["sources"]}
    return bool(locs & set(item["sources"])) or any(near_dup(item["text"], threads[k]["text"]) for k in resolved)


def drop_resolved_adds(adds, threads, resolved):
    """Add candidates minus the shadowed ones. 09-30: the older wording of RESULT_CALIB.md:204 was proposed for BACKLOG
    while its edited-in-place successor was listed as possibly closed -- one brief contradicting itself."""
    return [c for c in adds if not shadowed(c, threads, resolved)]


def split_suggested(suggested, verdicts):
    """Suggested closures whose evidence is a commit message go to a one-line 'likely closed' list: a commit message
    is a deliberate record, and on 09-30 the commit-backed ones were right on inspection. The rest (diary lines,
    same-day receipts) keep the longer 'check' format."""
    likely = [k for k in suggested if verdicts[k].get("ev", {}).get("source", "").startswith("commit ")]
    return likely, [k for k in suggested if k not in likely]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8099")
    ap.add_argument("--max-adjudicate", type=int, default=60)
    ap.add_argument("--render-only", action="store_true",
                    help="no model calls: re-render today's brief from verdicts_<date>.json (for tuning the brief)")
    a = ap.parse_args()
    today = datetime.date.today().isoformat()
    state_p = MORNING / "threads_state.json"
    state = json.load(open(state_p))
    links = json.load(open(MORNING / f"links_{today}.json"))
    status, notes, n_calls = "ok", [], 0

    # 1. adjudicate closure candidates (threads, then BACKLOG items)
    verdicts, bl_verdicts = {}, []
    todo = [(k, v) for k, v in links["threads"].items() if v["closure_candidates"]][: a.max_adjudicate]
    vpath = MORNING / f"verdicts_{today}.json"
    if a.render_only:
        saved = json.load(open(vpath))
        verdicts, bl_verdicts, picks = saved["verdicts"], saved["backlog"], saved["picks"]
        status, notes, n_calls = saved["status"], saved["notes"] + ["re-rendered without model calls"], saved["calls"]
        todo = todo[:saved.get("checked", len(todo))]
    try:
        if a.render_only:
            raise StopIteration
        for k, v in todo:
            src = v["sources"][0].split(":")[0]
            out = quick(a.host, ADJ.format(src=src, date=v["since"], text=v["text"][:900],
                                           evidence=fmt_evidence(v["closure_candidates"])))
            n_calls += 1
            j = last_json(out) or {"status": "open", "why": "unparseable verdict"}
            verdicts[k] = j
            if j.get("status") == "closed":
                ev = v["closure_candidates"][(j.get("evidence") or 1) - 1] if isinstance(j.get("evidence"), int) \
                    and 1 <= j["evidence"] <= len(v["closure_candidates"]) else v["closure_candidates"][0]
                j["ev"] = ev
                # Unattended closure is the risky direction (a wrong one silently drops a thread), so it is applied
                # only on a RECEIPT committed on a LATER day than the thread. Anything weaker is a suggestion.
                if ev["source"].startswith("data/receipts/") and ev["date"] > v["since"]:
                    state["threads"][k].update(status="closed", closed_on=today, closed_by=ev["source"],
                                               closed_why=j.get("why"))
                else:
                    j["status"] = "suggested"
        for it in links["backlog"]["close_candidates"][: a.max_adjudicate]:
            out = quick(a.host, ADJ.format(src="data/receipts/BACKLOG.md", date="(open item)", text=it["text"][:900],
                                           evidence=fmt_evidence(it["evidence"])))
            n_calls += 1
            j = last_json(out) or {"status": "open"}
            if j.get("status") in ("closed", "partly"):
                ev = it["evidence"][(j.get("evidence") or 1) - 1] if isinstance(j.get("evidence"), int) \
                    and 1 <= j["evidence"] <= len(it["evidence"]) else it["evidence"][0]
                bl_verdicts.append({**it, "verdict": j, "ev": ev})
    except StopIteration:
        pass
    except Exception as e:                                  # noqa: BLE001
        status = "degraded"; notes.append(f"adjudication stopped after {n_calls} calls: {type(e).__name__}: {e}")

    # 2. picks. A thread the adjudicator called closed on weaker evidence ("suggested") is listed for checking, not
    # picked: in the first unattended brief (09-28) four of five picks were already answered or shelved.
    every = {k: {"text": t["text"], "sources": t.get("sources", [])} for k, t in state["threads"].items()}
    resolved = ({k for k, t in state["threads"].items() if t["status"] != "open"}
                | {k for k, v in verdicts.items() if v.get("status") in ("closed", "suggested")})
    open_ids = [k for k in links["threads"] if k not in resolved
                and not shadowed({"thread": k, **links["threads"][k]}, every, resolved)]
    n_shadowed = sum(1 for k in links["threads"] if k not in resolved and k not in open_ids)
    ranked = sorted(open_ids, key=lambda k: (-state["threads"][k]["mentions"], state["threads"][k]["first_seen"]))[:25]
    if not a.render_only:
        picks = []
    if status == "ok" and ranked and not a.render_only:
        blob = "\n\n".join(
            f"[{k}] (mentioned {state['threads'][k]['mentions']}x, first seen {state['threads'][k]['first_seen']}, "
            f"from {links['threads'][k]['sources'][0]})\n{links['threads'][k]['text'][:600]}\n"
            + "".join(f"  related: {r['source']} ({r['date']}): {r['snippet'][:160]}\n" for r in links["threads"][k]["related"][:2])
            + (f"  PARTLY ANSWERED since: {verdicts[k].get('why', '')} -- the next step is what is left, not the answered part\n"
               if verdicts.get(k, {}).get("status") == "partly" else "")
            for k in ranked)
        try:
            try:
                out = think(a.host, PICK.format(threads=blob))
            except RuntimeError as e:                       # all reasoning, no answer: retry without thinking
                notes.append(f"picks: {e}; retried with thinking off")
                n_calls += 1
                out = quick(a.host, PICK.format(threads=blob), max_tokens=1800, timeout=1200)
            n_calls += 1
            arr = last_json(out, "[") or []
            picks = [p for p in arr if isinstance(p, dict) and p.get("id") in links["threads"]][:5]
            if not picks:
                notes.append("model returned no valid picks")
        except Exception as e:                              # noqa: BLE001
            status = "degraded"; notes.append(f"picks failed: {type(e).__name__}: {e}")

    # 3. brief
    closed_now = [k for k, v in verdicts.items() if v.get("status") == "closed"]
    suggested = [k for k, v in verdicts.items() if v.get("status") == "suggested" and state["threads"][k]["status"] == "open"]
    adds = drop_resolved_adds(links["backlog"]["add_candidates"], every, resolved)
    likely, check = split_suggested(suggested, verdicts)
    picked = {p["id"] for p in picks}
    adds.sort(key=lambda c: (-state["threads"][c["thread"]]["mentions"], state["threads"][c["thread"]]["first_seen"]))
    per_file, capped = {}, []                         # one receipt's caveats must not fill the list (09-28: 6 of 8)
    for c in adds:
        f = c["sources"][0].rpartition(":")[0]
        per_file[f] = per_file.get(f, 0) + 1
        if per_file[f] <= 2:
            capped.append(c)
    adds = capped
    L = [f"# Morning brief -- {today}", "",
         f"*Nightly daydream: {len(links['threads'])} open action threads from the last few days, "
         f"{len(todo)} checked for closure, {n_calls} model calls on {a.host} (status: {status}); "
         f"{n_shadowed} open thread(s) skipped as siblings of closed ones.*", ""]
    if notes:
        L += ["> " + n for n in notes] + [""]
    L += ["## Worth picking up", ""]
    if picks:
        for n, p in enumerate(picks, 1):
            t = links["threads"][p["id"]]
            L += [f"{n}. **{p.get('title', '').strip()}** `{p['id']}`",
                  f"   - Why: {p.get('why', '').strip()}",
                  f"   - Next: {p.get('next', '').strip()}",
                  f"   - From: `{t['sources'][0]}`" + (f"; related `{t['related'][0]['source']}`" if t["related"] else ""), ""]
    else:
        L += ["*(no model picks tonight; see the open threads below)*", ""]
    L += ["## Proposed BACKLOG.md edits (a session or Mark applies them; nothing here edits BACKLOG)", "",
          "### Looks closed or partly closed", ""]
    L += [f"- **{b['id']}** (line {b['line']}, {b['verdict']['status']}): {b['text'][:140]}...  \n"
          f"  evidence: `{b['ev']['source']}` ({b['ev']['date']}) -- {b['verdict'].get('why', '')}" for b in bl_verdicts] or ["- none"]
    L += ["", "### Not in BACKLOG yet (open action threads with no close match)", ""]
    L += [f"- {c['text'][:200]}  \n  from `{c['sources'][0]}` (nearest BACKLOG item {c['nearest']}, cos {c['cos']})"
          + (" -- also a pick above" if c["thread"] in picked else "") for c in adds[:8]] or ["- none"]
    L += ["", "## Threads closed tonight (marked in the state file)", ""]
    L += [f"- {state['threads'][k]['text'][:160]}  \n  by `{state['threads'][k]['closed_by']}`: {verdicts[k].get('why', '')}"
          for k in closed_now] or ["- none"]
    L += ["", "## Likely closed by a commit -- skim and close (left open until a session or Mark confirms)", ""]
    L += [f"- `{verdicts[k]['ev']['source'].split()[-1]}` ({verdicts[k]['ev']['date']}): "
          f"{re.sub(r'[*`]', '', state['threads'][k]['text'])[:110].strip()}" for k in likely] or ["- none"]
    L += ["", "## Possibly closed -- check (diary or same-day evidence; left open)", ""]
    L += [f"- {state['threads'][k]['text'][:160]}  \n  maybe by `{verdicts[k]['ev']['source']}` ({verdicts[k]['ev']['date']}): "
          f"{verdicts[k].get('why', '')}" for k in check] or ["- none"]
    L += ["", "## Recurring failure modes seen in the last 7 days (ledger_retro)", ""]
    L += retro_recent() or ["- none"]
    L += ["", "---", f"*Harvest `harvest_{today}.json`, links `links_{today}.json`, state `threads_state.json`.*"]
    MORNING.mkdir(parents=True, exist_ok=True)
    (MORNING / f"{today}.md").write_text("\n".join(L) + "\n")
    json.dump(state, open(state_p, "w"), indent=1, ensure_ascii=False)
    if not a.render_only:
        json.dump({"verdicts": verdicts, "backlog": bl_verdicts, "picks": picks, "status": status, "notes": notes,
                   "calls": n_calls, "checked": len(todo)}, open(vpath, "w"), indent=1, ensure_ascii=False)
    print(json.dumps({"status": status, "picks": len(picks), "closed": len(closed_now), "suggested": len(suggested), "likely": len(likely), "backlog_close": len(bl_verdicts),
                      "backlog_add": len(adds), "calls": n_calls, "notes": notes}))


if __name__ == "__main__":
    main()
