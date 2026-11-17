"""Loop labels for agent episodes (agentic-gaming/DESIGN_v1.md section 5). A label, never an ending.

Calls are compared in canonical form: the tool name plus its arguments as JSON with keys sorted at every level (the
form DeepSeek's repeat guard uses). Two clauses:
  exact   the call log is periodic with period p in 1..4 over at least max(6, 3p) calls;
  growing six consecutive calls with one tool, each at least 0.9 similar to the call before it AND at least 10
          characters longer: "the last command plus one more line", which the pilot showed exact matching misses.
          Requiring growth keeps honest probing (one function called with different inputs of similar length) and
          edit-and-rerun cycles from firing.
Thresholds were fitted on the 51 pilot episodes (13 loops, three models, two tasks): a description, not a validation.
"""
import difflib, json

NEAR, GROW, RUN = 0.9, 10, 6


def canon(call):
    return call["tool"], json.dumps(call.get("args", {}), sort_keys=True)


def label(log):
    """First firing of either clause over the non-finish calls, or None. Returns {step, kind, left_later}, where step is
    the index (in the non-finish call list) at which the rule fires and left_later says whether any later call broke the
    pattern (a loop the agent left)."""
    calls = [e for e in log if e.get("tool") != "finish"]
    sig = [canon(e) for e in calls]
    grow = [i > 0 and sig[i][0] == sig[i - 1][0] and len(sig[i][1]) >= len(sig[i - 1][1]) + GROW
            and difflib.SequenceMatcher(None, sig[i][1], sig[i - 1][1], autojunk=False).ratio() >= NEAR
            for i in range(len(sig))]
    for i in range(len(sig)):
        for p in (1, 2, 3, 4):
            n = 0
            while i - n - p >= 0 and sig[i - n] == sig[i - n - p]:
                n += 1
            if n and n + p >= max(6, 3 * p):
                return {"step": i, "kind": f"exact, period {p}",
                        "left_later": any(sig[j] != sig[j - p] for j in range(i + 1, len(sig)))}
        if i >= RUN - 1 and all(grow[i - k] for k in range(RUN - 1)):
            return {"step": i, "kind": "growing", "left_later": not all(grow[i + 1:])}
    return None


def stuck(log):
    """The table's row 8 test: the rule fired and the agent never left the loop."""
    lab = label(log)
    return bool(lab and not lab["left_later"])
