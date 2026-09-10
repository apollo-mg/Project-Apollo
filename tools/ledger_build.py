#!/usr/bin/env python3
"""Build a dev-diary ledger entry from a Claude Code session transcript.

THE PROBLEM THIS SOLVES. Context is lost at every compaction, and what survives in receipts is
RESULTS. What gets lost is REASONS -- and reasons are what stop work being redone. Concrete
losses from 2026-08-26 alone:
  * three Llama order-test runs, because ladder AND floor both had to match and only one axis
    was checked per iteration
  * min_p=0.05 inherited from a llama.cpp default for hours, unnoticed until /props was read
  * TOOL-FAIL conflating "the tool broke" with "the agent never tried it"
  * DFlash's dual-context nature re-derived from an error message when it was already written
    down in a receipt on 08-18
None of those appear in a list of tool calls. They are all *why*.

DESIGN. The model is NOT asked to discover what mattered from 600 events -- that is the hard
part and a 9B will do it badly. Instead a SKELETON is extracted mechanically (errors, retries,
corrections, artifacts) and the model writes the reasoning around a structure it did not have
to find. Local model only; no cloud.

Robustness: if the model call fails, the skeleton is written anyway. A mechanical ledger beats
no ledger.
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request
from collections import Counter, defaultdict
from datetime import datetime

def load_events(path):
    ev=[]
    for line in open(path, errors="replace"):
        line=line.rstrip("\n")
        if not line: continue
        kind, _, rest = line.partition("  ")
        ev.append((kind.strip(), rest.strip()))
    return ev

def skeleton(ev):
    """Mechanically extract the spine. No model judgement involved."""
    s = {"errors": [], "retries": [], "corrections": [], "artifacts": [], "tools": Counter()}
    # Retry detection keys on REPEATED SIMILAR COMMANDS, not consecutive same-tool calls.
    # First version counted "Bash x130", which is just Bash being the primary tool -- no signal.
    # A near-identical command issued 3+ times means something was fighting back.
    sigs = Counter(); exemplar = {}
    for i,(k,v) in enumerate(ev):
        if k == "TOOL":
            name = v.split()[0] if v else "?"
            s["tools"][name] += 1
            arg = v.split("  ",1)[1] if "  " in v else ""
            # signature = tool + first 60 chars of the arg, alphanumerics only, so trivial
            # differences (paths, ports, timestamps) still collapse to one signature
            sig = name + "|" + re.sub(r"[^a-z]", "", arg.lower())[:60]
            if len(sig) > 12:
                sigs[sig] += 1
                exemplar.setdefault(sig, arg[:90])   # readable form for the report
            m = re.search(r"file_path=(\S+)", v)
            if m: s["artifacts"].append(m.group(1))
        elif k == "ERR":
            s["errors"].append(v[:140])
        elif k == "HUMAN":
            # short human turns right after assistant prose are usually corrections/redirects
            if len(v) < 320 and i and ev[i-1][0] == "SAY":
                s["corrections"].append(v[:220])
    s["retries"] = [(f'{k.split("|")[0]}: {exemplar.get(k,"")}', n)
                    for k, n in sigs.most_common(12) if n >= 3]
    s["artifacts"] = [a for a,_ in Counter(s["artifacts"]).most_common(25)]
    return s

PROMPT = """You are writing one section of an engineering dev diary for a local-LLM research project.

Below is a mechanically-extracted skeleton of a work session, plus the raw event stream. Write a
concise diary entry in markdown covering ONLY this window.

Rules:
- Lead with what was DECIDED and WHY, not a list of what was run.
- Every error, retry loop and human correction in the skeleton exists because something went
  wrong. Explain the cause where the events support it. Do not invent causes.
- Record dead ends and false starts explicitly. They are the most valuable content: they stop
  the work being redone.
- If a claim was corrected or retracted, say so plainly.
- Be specific: file names, numbers, flags. No filler, no praise, no summary of the summary.
- 200-400 words.
- Headings MUST start at level 3 (###) or lower. Level 1 and 2 are reserved for the
  day and run wrappers; using them makes your sections siblings of the run header and
  the file becomes unreadable once several runs have appended.

## SKELETON
{skel}

## EVENTS
{events}
"""

def strip_reasoning(text):
    """Remove chain-of-thought from a completion, keeping every scrap of real prose.

    NOT a `<think>.*?</think>` regex alone. Qwen-family templates pre-fill the OPENING <think>
    inside the prompt, so the completion carries only a CLOSING tag and a paired regex matches
    nothing -- that is how 58% of the 2026-08-30 entry became the model's reasoning, surfacing
    only when the .73 wake-proxy fallback (Qwen3.8-27B, reasoning_effort=medium) served a run
    for the first time. The .194 endpoints emit no think blocks at all.

    Nor is it "cut through the LAST closing tag". That was the first fix and it was wrong: the
    same entry carried a SECOND, unpaired </think> in the middle of the prose, so cutting to the
    last one silently deleted 1.3 KB of finished entry. A stray closing tag is far more likely
    than a complete second reasoning block that somehow has no opening tag.

    So: drop paired blocks, treat the FIRST unpaired closing tag as the end of the pre-filled
    block, and downgrade anything after that to a stray marker worth deleting but not obeying.
    """
    # 1. Models that emit their own opening tag: remove the whole span.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    # 2. A closing tag with no opener => the template pre-filled <think> in the prompt.
    i = text.find("</think>")
    if i != -1:
        text = text[i + len("</think>"):]
    # 3. Further closing tags are noise inside the prose. Drop the marker, KEEP the text.
    text = text.replace("</think>", "")
    # 4. An opening tag still standing means the model was truncated mid-thought and there is no
    #    entry in here at all. Return nothing; the caller writes the mechanical skeleton, which
    #    is honest, rather than publishing reasoning as prose.
    if "<think>" in text:
        return ""
    return text.strip()

def call_model(host, prompt, model=None, timeout=1800):
    # 6144, not 2048. A reasoning model spends its budget thinking BEFORE it writes anything, so
    # a budget sized for a non-reasoning endpoint gets consumed mid-thought and the "entry" is
    # pure chain-of-thought with no closing tag to strip. That is exactly what the 2026-08-30
    # 12:45 run produced. 400 words of entry needs ~600 tokens; the rest is headroom to think.
    body={"messages":[{"role":"user","content":prompt}],"max_tokens":6144,"temperature":0.4,
          "chat_template_kwargs":{"reasoning_effort":"medium"}}
    if model: body["model"]=model
    r=urllib.request.Request(host.rstrip("/")+"/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f: d=json.loads(f.read())
    ch = d["choices"][0]
    m = ch["message"]
    # Prefer content; some servers split reasoning into its own field, in which case content is
    # already clean. Strip either way -- llama-server with this template returns the whole thing,
    # think block included, in content.
    text = strip_reasoning(m.get("content") or m.get("reasoning_content") or "")
    # finish_reason is the ONLY reliable truncation signal. Heuristics on the prose cannot tell a
    # cut-off entry from a terse one, and a run that stopped on length never reached its closing
    # think tag, so nothing was stripped and the "entry" is raw reasoning. Refusing here makes
    # the caller fall back to the mechanical skeleton and the beat record it, which is honest.
    if ch.get("finish_reason") == "length" and "</think>" not in (m.get("content") or ""):
        raise RuntimeError("model hit the token limit before writing an entry (all reasoning)")
    return text

def render_skeleton(s):
    L=[]
    L.append(f"- tool calls: {sum(s['tools'].values())} "
             f"({', '.join(f'{k} x{v}' for k,v in s['tools'].most_common(6))})")
    if s["errors"]:
        L.append(f"- errors ({len(s['errors'])}):")
        for e in s["errors"][:12]: L.append(f"    * {e}")
    if s["retries"]:
        L.append("- repeated near-identical commands (>=3x — something was fighting back):")
        for t,n in s["retries"][:10]: L.append(f"    * {t} x{n}")
    if s["corrections"]:
        L.append(f"- short human turns following assistant prose (likely corrections/redirects):")
        for c in s["corrections"][:12]: L.append(f"    * {c}")
    if s["artifacts"]:
        L.append("- files touched: " + ", ".join(os.path.basename(a) for a in s["artifacts"][:18]))
    return "\n".join(L)

def main(a):
    ev = load_events(a.events)
    if not ev: print("no events", file=sys.stderr); return 1
    s = skeleton(ev)
    skel = render_skeleton(s)
    raw = "\n".join(f"{k} {v}" for k,v in ev)[-a.max_chars:]
    entry = None
    if not a.skeleton_only:
        try:
            entry = call_model(a.host, PROMPT.format(skel=skel, events=raw), a.model)
        except Exception as e:
            print(f"model call failed: {type(e).__name__}: {e}", file=sys.stderr)
    # Validate BEFORE appending. `/health` returning 200 says a server is up, not that the model
    # loaded into it is sane -- on 2026-08-28 a .194 endpoint held a model in a known-broken
    # tensor-split config and cheerfully returned 200 while generating `////////`. Refusing here
    # lets ledger_run.sh fall through to the NEXT endpoint instead of committing to the first one
    # that answered. An invalid entry that was never written cannot be alerted on later.
    if entry and not a.no_validate:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from ledger_validate import classify
        bad = classify(entry)
        if bad:
            print(f"REJECTED entry from {a.host}: {bad}", file=sys.stderr)
            return 2

    day = datetime.now().strftime("%Y-%m-%d")
    out = a.out or f"/mnt/TG_2TB/Projects/Apollo/data/dev_diaries/{day}_ledger.md"
    stamp = datetime.now().strftime("%H:%M")
    with open(out, "a") as f:
        f.write(f"\n\n## {stamp} — {len(ev)} events\n\n")
        if entry:
            # Belt and braces: demote stray #/## the model emits despite the instruction.
            # Prompt compliance is not a contract, and one bad heading breaks the whole day's file.
            entry = re.sub(r"^(#{1,2})(?!#)\s", "### ", entry, flags=re.M)
            f.write(entry + "\n")
        else:     f.write("_(model unavailable — mechanical skeleton only)_\n")
        f.write(f"\n<details><summary>skeleton</summary>\n\n```\n{skel}\n```\n</details>\n")
    print(f"appended {len(ev)} events -> {out}")
    return 0

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("events", help="output of ledger_extract.py")
    p.add_argument("--host", default="http://10.0.0.194:8086")
    p.add_argument("--model")
    p.add_argument("--out")
    p.add_argument("--no-validate", action="store_true",
                   help="append even if the entry looks malformed (debugging only)")
    p.add_argument("--max-chars", type=int, default=400000)
    p.add_argument("--skeleton-only", action="store_true")
    sys.exit(main(p.parse_args()))
