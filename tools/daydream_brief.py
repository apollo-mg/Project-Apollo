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
Stage 2b (one question for Mark) never asks about a thread that BACKLOG.md records as settled (backlog_settled());
the skipped ids and the matching BACKLOG snippets go to `question_skipped_settled` in the JSON output.

Usage: daydream_brief.py [--host http://127.0.0.1:8099] [--max-adjudicate 60] [--render-only]
"""
import argparse, datetime, json, re, subprocess, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ledger_build import strip_reasoning  # noqa: E402  (the ledger's tested call + think stripping)
from daydream_harvest import anchors  # noqa: E402  (the harvest's strong-anchor extractor, COMMIT_RX included)

MORNING = ROOT / "data" / "dev_diaries" / "morning"
BACKLOG = ROOT / "data" / "receipts" / "BACKLOG.md"


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


ASK = """You are the night-shift reviewer for a solo hardware-empirics lab, and tonight you may ask Mark ONE question, or none.
Ask only when his answer changes what happens next: whether a thread is worth finishing, should be dropped, or can be
parked, or a fact only he knows. Prefer threads that keep coming back without progress (mentioned many times, open for
many days): those are the half-finished things that cost him most. A hunch is allowed: if several threads point at one
pattern, ask whether it is real, and say it is a hunch. Do not ask what the threads already answer, and do not invent
commands, file paths or commit ids. If nothing tonight is worth his attention, ask nothing: an unneeded question costs
more than a missed one.

THREADS:
{threads}

Reply with one line of JSON only:
{{"ask": true | false, "kind": "decide" | "clarify" | "hunch", "id": "<thread id>", "question": "<one sentence he can answer in a few words>", "why": "<one sentence: what his answer changes>"}}"""


def unpark(state, today):
    """A parked thread (daydream_close.py --answer park) comes back on its date."""
    back = [k for k, t in state["threads"].items() if t["status"] == "parked" and t.get("park_until", "9999") <= today]
    for k in back:
        state["threads"][k]["status"] = "open"
    return back


# --- settled BACKLOG evidence (2026-11-03) ----------------------------------------------------------------------------
# The first live question asked whether the .73 daily driver should switch to `1c5e564b`; BACKLOG row N2 had recorded
# that switch as done five weeks earlier (struck id, "**DONE 10-02:**", and "~~.73 daily driver to `1c5e564b`~~ **done
# via `510cbbbfa`**"). A question is not asked when one of the thread's commit ids or file names appears in what
# BACKLOG records as settled. Precision first: a wrong skip silently hides an open item, so only strong anchors count
# (never a shared word), and text after an "open" marker inside a done item is not settled.
SETTLED_KINDS = ("commit", "file", "ident")      # what settled evidence may carry (backticked identifiers included)
THREAD_KINDS = ("commit", "file")                # what a thread may be skipped on
DONE_RX = re.compile(r"\*\*\s*(?:DONE|FIXED)\b")
STRUCK_RX = re.compile(r"~~(.+?)~~")
STRUCK_ID_RX = re.compile(r"^\|\s*~~[^~|]+~~\s*\|")
OPEN_RX = re.compile(r"\b(?:still|also|remains?|left) open\b|\bopen follow-?up|\bstill (?:on|to do|todo|untested|pending)\b|"
                     r"\bnot yet\b|\buntested\b|\bremaining\b|\bblocked\b|\bmark's call\b|\bpartly\b", re.I)


def _strong(text, kinds=SETTLED_KINDS):
    return {a: k for a, k in anchors(text).items() if k in kinds}


def _settled_segments(body, whole):
    """The settled parts of a done item, struck spans removed (they are evidence of their own): from the start when the
    whole item is done, and from every **DONE/**FIXED marker; each part ends at the next open marker."""
    starts = ([0] if whole else []) + [m.start() for m in DONE_RX.finditer(body)]
    segs, end = [], -1
    for s in sorted(set(starts)):
        if s < end:                                       # inside the part before it: already counted
            continue
        m = OPEN_RX.search(body, s + 2)
        end = m.start() if m else len(body)
        segs.append(body[s:end])
    return segs


def backlog_settled(text):
    """BACKLOG.md text -> [{line, kind, snippet, anchors}] for what it records as settled: rows whose id cell is struck
    (`| ~~N2~~ |`), rows and bullets that start with or contain **DONE** / **FIXED**, and every ~~struck span~~ (which
    settles only what is inside it). Only commit ids, backticked identifiers and file names are kept as anchors."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        is_row, is_bullet = s.startswith("|"), bool(re.match(r"^(?:[-*+]|\d+[.)])\s", s))
        if not (is_row or is_bullet):
            continue
        for m in STRUCK_RX.finditer(s):
            anc = _strong(m.group(1))
            if anc:
                out.append({"line": n, "kind": "struck", "snippet": m.group(0)[:200], "anchors": anc})
        body = STRUCK_RX.sub(" ", s)
        if is_row:
            cells = [c.strip() for c in body.strip("|").split("|")]
            first = cells[1] if len(cells) > 1 else ""
            body = " | ".join(cells[1:])                          # the id cell carries no anchors
        else:
            first = body = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", body)
        whole = bool(STRUCK_ID_RX.match(s)) or bool(re.match(r"\*\*\s*(?:DONE|FIXED)\b", first))
        if not (whole or DONE_RX.search(body)):
            continue
        for seg in _settled_segments(body, whole):
            anc = _strong(seg)
            if anc:
                out.append({"line": n, "kind": "struck-id" if whole and STRUCK_ID_RX.match(s) else "done",
                            "snippet": seg.strip()[:200], "anchors": anc})
    return out


def load_backlog_settled(path=BACKLOG):
    """No BACKLOG file -> no settled evidence -> stage 2b behaves exactly as before."""
    try:
        return backlog_settled(Path(path).read_text())
    except OSError:
        return []


def settled_by(text, settled):
    """{"anchors": [...], "backlog": [...]} when one of the thread's commit ids or file names is in settled BACKLOG
    evidence, else None."""
    mine = _strong(text, THREAD_KINDS)
    order = {"struck": 0, "struck-id": 1, "done": 2}    # the most specific evidence first
    hits = sorted((e for e in settled if mine.keys() & e["anchors"].keys()), key=lambda e: (order[e["kind"]], e["line"]))
    if not hits:
        return None
    return {"anchors": sorted({a for e in hits for a in e["anchors"] if a in mine}),
            "backlog": [{"line": e["line"], "kind": e["kind"], "snippet": e["snippet"]} for e in hits[:3]]}


def _skip(state, k, settled, skipped):
    hit = settled_by(state["threads"][k].get("text", ""), settled) if settled else None
    if hit and skipped is not None:
        skipped.append({"id": k, **hit})
    return bool(hit)


def interpret_ask(j, cand):
    """The ASK reply's JSON -> (question with its thread id, None) or (None, a note saying why nothing was asked).
    2026-11-05: two nights asked nothing with 20 candidates and left no trace of whether the model declined or its reply
    did not parse; every no-question path now says which."""
    if not j:
        return None, "question: the reply had no JSON object (nothing asked)"
    if not j.get("ask"):
        why = str(j.get("why", "")).strip()
        return None, "question: the model chose to ask nothing" + (f" ({why[:160]})" if why else "")
    if j.get("id") not in cand:
        return None, f"question: the reply named {str(j.get('id'))[:20]!r}, not one of the {len(cand)} candidates (nothing asked)"
    if not str(j.get("question", "")).strip():
        return None, "question: the reply's question was empty (nothing asked)"
    return {"id": j["id"], **{k: str(j.get(k, "")).strip() for k in ("kind", "question", "why")}}, None


def pending_question(state, settled=(), skipped=None):
    """The thread asked about and not answered yet: one open question at a time. One that BACKLOG records as settled
    is not shown again (it is recorded in `skipped`; its state is left for a session or Mark to close)."""
    return next((k for k, t in state["threads"].items() if t.get("asked_on") and not t.get("answer") and t["status"] == "open"
                 and not _skip(state, k, settled, skipped)), None)


def question_candidates(state, today, n=20, settled=(), skipped=None):
    """Open action threads that keep coming back, never asked about: mentions times days open ranks them. Threads that
    BACKLOG records as settled are dropped before ranking and recorded in `skipped`."""
    age = lambda t: (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(t["first_seen"])).days
    c = [k for k, t in state["threads"].items() if t["status"] == "open" and t.get("kind", "action") == "action"
         and not t.get("asked_on") and not t.get("answer") and (t["mentions"] >= 2 or age(t) >= 7)]
    c = [k for k in c if not _skip(state, k, settled, skipped)]
    return sorted(c, key=lambda k: (-state["threads"][k]["mentions"] * (1 + age(state["threads"][k])), state["threads"][k]["first_seen"]))[:n]


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
    saved = {}
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

    # 2b. one question for Mark (2026-11-02, Mark: "it should be asking us questions"). The brief summarised 136 threads
    # and asked nothing. One open question at a time; an unanswered one is shown again, three times in all, then parked
    # for 30 days so it cannot nag. A failure here is a note, not a degraded brief.
    q = saved.get("question") if a.render_only else None
    q_raw_tail = None                                     # the ASK reply's tail when nothing was asked (audit)
    settled, q_skipped = load_backlog_settled(), []
    if a.render_only:                                     # dry run: report what the settled check would skip, change nothing
        pending_question(state, settled, q_skipped)
        question_candidates(state, today, settled=settled, skipped=q_skipped)
    if not a.render_only:
        back = unpark(state, today)
        if back:
            notes.append(f"{len(back)} parked thread(s) came back today")
        pend = pending_question(state, settled, q_skipped)
        if pend:
            t = state["threads"][pend]
            if t.get("asked_times", 1) >= 3:
                t.update(status="parked", park_until=(datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
                         parked_why="asked three times, no answer")
                notes.append(f"question about `{pend}` went unanswered three times; parked for 30 days")
            else:
                t["asked_times"] = t.get("asked_times", 1) + 1
                q = {**t["question"], "id": pend, "repeat": t["asked_times"]}
        elif status == "ok":
            cand = question_candidates(state, today, settled=settled, skipped=q_skipped)
            if cand:
                blob = "\n\n".join(f"[{k}] (mentioned {state['threads'][k]['mentions']}x, open since {state['threads'][k]['first_seen']}, "
                                   f"from {state['threads'][k]['sources'][0] if state['threads'][k]['sources'] else 'unknown'})\n"
                                   f"{state['threads'][k]['text'][:500]}" for k in cand)
                try:
                    try:
                        out = think(a.host, ASK.format(threads=blob))
                    except RuntimeError as e:
                        notes.append(f"question: {e}; retried with thinking off")
                        n_calls += 1
                        out = quick(a.host, ASK.format(threads=blob), max_tokens=500, timeout=900)
                    n_calls += 1
                    qq, why_not = interpret_ask(last_json(out), cand)
                    if qq:
                        state["threads"][qq["id"]].update(asked_on=today, asked_times=1, question={k: qq[k] for k in ("kind", "question", "why")})
                        q = {**qq, "repeat": 1}
                    else:
                        notes.append(why_not)
                        q_raw_tail = (out or "")[-400:]
                except Exception as e:                      # noqa: BLE001
                    notes.append(f"question failed: {type(e).__name__}: {e}")
            else:
                notes.append("question: no candidates tonight (nothing asked)")

    if q_skipped:
        notes.append(f"question: {len(q_skipped)} thread(s) skipped as settled in BACKLOG.md "
                     f"({', '.join('`' + x['id'] + '`' for x in q_skipped[:5])}); see question_skipped_settled")

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
    if q:
        L += ["## One question for you", "", f"**{q['question']}**", "",
              f"- {q.get('kind') or 'decide'}, about `{q['id']}`: {re.sub(r'[*`]', '', state['threads'][q['id']]['text'])[:220].strip()}",
              f"- Why ask: {q.get('why', '')}" + (f" (asked {q['repeat']} times)" if q.get("repeat", 1) > 1 else ""),
              f"- Answer: `tools/daydream_close.py --answer finish|drop|park|note {q['id']}`, with `--why \"...\"` for the "
              f"reason or the fact, or tell a session.", ""]
    finish = [k for k, t in state["threads"].items() if t.get("answer") == "finish" and t["status"] == "open"]
    if finish:
        L += ["## You said finish (still open)", ""]
        L += [f"- `{k}` (since {state['threads'][k]['answered_on']}): {re.sub(r'[*`]', '', state['threads'][k]['text'])[:140].strip()}"
              for k in finish[:5]] + [""]
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
                   "calls": n_calls, "checked": len(todo), "question": q, "question_skipped_settled": q_skipped,
                   "question_raw_tail": q_raw_tail},
                  open(vpath, "w"), indent=1, ensure_ascii=False)
    print(json.dumps({"status": status, "picks": len(picks), "closed": len(closed_now), "suggested": len(suggested), "likely": len(likely), "backlog_close": len(bl_verdicts),
                      "backlog_add": len(adds), "calls": n_calls, "notes": notes, "question": (q or {}).get("question", ""),
                      "question_skipped_settled": q_skipped}))


if __name__ == "__main__":
    main()
