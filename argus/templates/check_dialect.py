#!/usr/bin/env python3
"""Round-trip a model's rendered tool call against the parser that will read it.

Catches the class of defect in AFM-41: llama.cpp selects a specialized tool-call
parser by substring-matching the TEMPLATE SOURCE, but that parser hardcodes a
whitespace dialect the template may not render. When they disagree, a string
argument runs past its own close tag and swallows the tool calls that follow --
HTTP 200, finish_reason=tool_calls, no error anywhere.

Deterministic. No sampling, no reps. Point it at a running llama-server.

    ./check_dialect.py http://127.0.0.1:8090

Exit 0 = the rendered form carries the literals the qwen3-coder parser needs,
         or that parser is not the one in play.
Exit 2 = MISMATCH: expect silent argument corruption on multi-call turns.
"""
import json, sys, urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8090").rstrip("/")

TOOLS = [{"type": "function", "function": {
    "name": "probe_alpha", "description": "First probe tool.",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                   "required": ["query"]}}},
         {"type": "function", "function": {
    "name": "probe_beta", "description": "Second probe tool.",
    "parameters": {"type": "object", "properties": {"start": {"type": "string"}},
                   "required": ["start"]}}}]

# An assistant turn that MADE two tool calls, plus their responses -- the tool
# responses are required or the server rejects the trailing assistant message.
MSGS = [
    {"role": "user", "content": "do two things"},
    {"role": "assistant", "content": "", "tool_calls": [
        {"id": "c1", "type": "function",
         "function": {"name": "probe_alpha", "arguments": json.dumps({"query": "v1"})}},
        {"id": "c2", "type": "function",
         "function": {"name": "probe_beta", "arguments": json.dumps({"start": "v2"})}}]},
    {"role": "tool", "tool_call_id": "c1", "content": "[]"},
    {"role": "tool", "tool_call_id": "c2", "content": "[]"},
]

# What common/parsers/qwen3-coder.cpp requires, verbatim.
REQUIRED = ["<tool_call>\n", "<function=probe_alpha>\n", "<parameter=query>\n",
            "\n</parameter>\n", "</function>\n"]


def main():
    # GROUND TRUTH for the dispatch: llama.cpp tests the template SOURCE, not its
    # rendered output. /props returns the source the server actually loaded, which
    # is the only way to see it from outside. An earlier version of this script
    # tested the fingerprint against the RENDERED prompt and reported a false
    # MISMATCH on a template that was being parsed correctly -- the two differ
    # exactly in the case this check exists to find. ([[readiness-probes-lie]])
    try:
        props = json.loads(urllib.request.urlopen(BASE + "/props", timeout=60).read())
    except Exception as e:
        print(f"could not reach {BASE}/props: {e}")
        return 1
    src = props.get("chat_template") or ""
    if not src:
        print("/props returned no chat_template; cannot determine the parser.")
        return 1

    # common/chat.cpp:1213 -- all three must appear in the SOURCE.
    fingerprint = ("<tool_call>", "<function=", "<parameter=")
    claimed = all(m in src for m in fingerprint)

    req = urllib.request.Request(
        BASE + "/apply-template",
        json.dumps({"messages": MSGS, "tools": TOOLS}).encode(),
        {"Content-Type": "application/json"})
    try:
        prompt = json.loads(urllib.request.urlopen(req, timeout=60).read())["prompt"]
    except Exception as e:
        print(f"could not reach {BASE}/apply-template: {e}")
        return 1

    print("dispatch fingerprint in template SOURCE (common/chat.cpp:1213):")
    for m in fingerprint:
        print(f"  {m!r:16s} {'present' if m in src else 'ABSENT'}")
    print(f"  => specialized qwen3-coder parser claimed: {claimed}")

    if not claimed:
        print("\nPASS: the specialized parser is not selected for this template.")
        print("  The generic auto-parser handles it, and that parser relaxes")
        print("  whitespace on ending markers (chat-diff-analyzer.cpp:884).")
        return 0

    i = prompt.find("<tool_call>")
    if i < 0:
        print("\nPASS (not applicable): template renders no '<tool_call>'.")
        return 0
    rendered = prompt[i:]
    print(f"\nrendered tool-call region:\n  {rendered[:200]!r}\n")
    missing = [m for m in REQUIRED if m not in rendered]
    for m in REQUIRED:
        print(f"  {m!r:32s} {'ok' if m in rendered else 'MISSING'}")

    if not missing:
        print("\nPASS: rendered form carries every literal the parser requires.")
        return 0
    print(f"\nMISMATCH: {len(missing)} of {len(REQUIRED)} required literals absent,")
    print("  and the specialized parser IS selected.")
    print("Expect silent argument corruption on turns with 2+ tool calls.")
    print("See data/receipts/mtp-transfer/RESULT_MIMO_TOOLCALL_DIALECT.md (AFM-41).")
    return 2


if __name__ == "__main__":
    sys.exit(main())
