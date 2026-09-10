"""Normalised iteration over an agent trace's tool calls.

WHY THIS EXISTS. Two changes in hermes-agent broke every verifier that matches a tool by name:

1. `feat(tool-search)` (e16ad33a9d, 2026-08-29) moved 19 core tools *behind the discovery
   bridge by default*. They are now invoked as
   `tool_call{name: "<real tool>", arguments: {...}}` rather than as a top-level call, so a
   check for `function.name == "process"` never fires no matter what the model did.

2. The same commit renamed several tools — `process` -> `process_manage` among them.

Verifiers written before that see a correct agent as having used no tools at all. Measured
2026-09-08: 7 of 14 non-passes in one run, and 6 of 9 in another, were correct tool use graded
as absent — including "expected >=2 todo calls, got 0" against two successful calls.

`iter_tool_calls` unwraps the dispatcher and maps renamed tools back to the names verifiers
already use, so existing checks work unmodified against both old and new agents.
"""
import json

# Renamed by e16ad33a9d. Map new -> legacy so verifiers keep matching the name they know.
_ALIASES = {
    "process_manage": "process",
    "cronjob_manage": "cronjob",
    "todo_list":      "todo",
}


def _as_dict(v):
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            d = json.loads(v)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}
    return {}


def iter_tool_calls(trace):
    """Yield (name, args) for every tool call in an assistant message.

    Dispatcher calls are unwrapped to the tool they invoke. Renamed tools are reported under
    their legacy names. `args` is always a dict.
    """
    for msg in trace or []:
        if msg.get("role") != "assistant":
            continue
        for tc in (msg.get("tool_calls") or []):
            fn = tc.get("function") or {}
            name = fn.get("name")
            args = _as_dict(fn.get("arguments"))
            if name == "tool_call":
                inner = args.get("name")
                if not inner:
                    continue
                name, args = inner, _as_dict(args.get("arguments"))
            yield _ALIASES.get(name, name), args


def used_tool(trace, name, **must_match):
    """True if `name` was called with every key in must_match equal in its arguments."""
    for n, a in iter_tool_calls(trace):
        if n != name:
            continue
        if all(a.get(k) == v for k, v in must_match.items()):
            return True
    return False


def count_tool(trace, name):
    return sum(1 for n, _ in iter_tool_calls(trace) if n == name)


def normalise_trace(trace):
    """Return the trace with dispatcher-wrapped tool calls unwrapped and renamed tools
    mapped back to their legacy names.

    Applied once by the runner before the verifier sees the trace, so every existing verifier
    keeps working against both pre- and post-2026-08-29 agents without being modified.
    `arguments` is re-emitted as a JSON string, which is what verifiers already parse.
    """
    out = []
    for msg in trace or []:
        if msg.get("role") != "assistant" or not msg.get("tool_calls"):
            out.append(msg)
            continue
        new_msg = dict(msg)
        calls = []
        for tc in msg["tool_calls"]:
            fn = dict(tc.get("function") or {})
            name = fn.get("name")
            args = _as_dict(fn.get("arguments"))
            if name == "tool_call":
                inner = args.get("name")
                if not inner:
                    calls.append(tc)          # malformed dispatch: leave it alone
                    continue
                name, args = inner, _as_dict(args.get("arguments"))
            fn["name"] = _ALIASES.get(name, name)
            fn["arguments"] = json.dumps(args)
            new_tc = dict(tc)
            new_tc["function"] = fn
            calls.append(new_tc)
        new_msg["tool_calls"] = calls
        out.append(new_msg)
    return out
