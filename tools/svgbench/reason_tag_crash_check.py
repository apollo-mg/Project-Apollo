#!/usr/bin/env python3
"""Reproduce the {REASON:} scanner crash in DavidAU's Twin-Turbo template, and verify donboyle's fix.

The scanner splits on the literal "{REASON:" in EVERY message with no role guard and no validation
of what it extracts, then a later allow-list check raises. Any text quoting the tag syntax -- a tool
result, or a user asking how the tag works -- therefore 500s the request.

donboyle's fix (discussion #10) adds two guards: only user messages are scanned, and the extracted
key must be in the allow-list. Garbage is ignored instead of raising.

Usage: reason_tag_crash_check.py MERGED.jinja
"""
import sys
from jinja2.sandbox import ImmutableSandboxedEnvironment

OLD = '''  {% if "{REASON:" in txt %}
    {% set after_tag = txt.split("{REASON:") %}
    {% set raw_reason = after_tag[1].split("}")[0] %}
'''
NEW = '''  {% set candidate = txt.split("{REASON:")[1].split("}")[0] if (msg.role == 'user' and "{REASON:" in txt) else "" %}
  {% set candidate_key = candidate[1:] if candidate.startswith('i') else candidate %}
  {% if candidate and candidate_key in ('xhigh', 'medium', 'low', 'einstein', 'spoon') %}
    {% set raw_reason = candidate %}
'''
TOOLS = [{"type": "function", "function": {"name": "get_weather", "parameters": {
    "type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}]
CALL = [{"id": "c1", "type": "function",
         "function": {"name": "get_weather", "arguments": '{"city":"Paris"}'}}]
POISON = 'Doc excerpt: the template checks {% if "{REASON:" in txt %} before splitting.'
U = lambda t: [{"role": "user", "content": t}]
CASES = {
    # --- the two paths found in the wild ---
    "poisoned tool result": [{"role": "user", "content": "Weather in Paris?"},
                             {"role": "assistant", "content": "", "tool_calls": CALL},
                             {"role": "tool", "content": POISON, "name": "get_weather"}],
    "user quotes the tag":  U('How does {REASON:" in txt %} parsing work?'),
    # --- valid modes, must keep working ---
    "valid xhigh":          U("{REASON:xhigh} hi"),
    "valid einstein":       U("{REASON:einstein} hi"),
    "valid spoon":          U("{REASON:spoon} hi"),
    "valid i-prefix":       U("{REASON:ieinstein} hi"),
    "{REASON:medium}":      U("{REASON:medium} What is 2+2?"),
    "{REASON:ixhigh}":      U("{REASON:ixhigh} What is 2+2?"),
    # --- ordinary user typos: these 500 on the shipped parser ---
    "typo: high":           U("{REASON:high} hi"),
    "typo: CAPS mode":      U("{REASON:EINSTEIN} hi"),
    "typo: missing brace":  U("{REASON:einstein hi"),
    "typo: whitespace":     U("{REASON: } hi"),
    # --- structural oddities ---
    "inner brace":          U("{REASON:ein{stein} hi"),
    "500-char value":       U("{REASON:" + "x" * 500 + "} hi"),
    "empty value":          U("{REASON:} hi"),
    "two tags":             U("{REASON:low} and {REASON:einstein} hi"),
    "tag in system msg":    [{"role": "system", "content": "{REASON:einstein}"},
                             {"role": "user", "content": "hi"}],
    "tag in assistant msg": [{"role": "user", "content": "a"},
                             {"role": "assistant", "content": "{REASON:einstein}"},
                             {"role": "user", "content": "b"}],
    "benign tool loop":     [{"role": "user", "content": "Weather in Paris?"},
                             {"role": "assistant", "content": "", "tool_calls": CALL},
                             {"role": "tool", "content": "18C and sunny", "name": "get_weather"}],
}


def env():
    e = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
    e.globals["raise_exception"] = lambda m: (_ for _ in ()).throw(Exception(m))
    e.globals["strftime_now"] = lambda f: "2026-09-12"
    return e


def render(tpl, msgs):
    try:
        return True, env().from_string(tpl).render(messages=msgs, tools=TOOLS, add_generation_prompt=True)
    except Exception as e:
        return False, str(e)[:100]


def main():
    tpl = open(sys.argv[1]).read()
    if tpl.count(OLD) != 1:
        sys.exit(f"scanner block not found exactly once ({tpl.count(OLD)}); template has changed")
    patched = tpl.replace(OLD, NEW)
    print(f"{'case':24s} {'as shipped':>12s} {'patched':>10s}   notes")
    bad = 0
    for name, msgs in CASES.items():
        ok1, o1 = render(tpl, msgs)
        ok2, o2 = render(patched, msgs)
        note = "" if ok2 else f"still fails: {o2}"
        if ok1 and "tool" in name and "<tool_call>" not in o1:
            note = "tool_call MISSING (the other bug)"
        bad += (not ok2)
        print(f"  {name:22s} {'OK' if ok1 else 'CRASH':>12s} {'OK' if ok2 else 'CRASH':>10s}   {note}")
    print("\npatched template: all cases render" if not bad else f"\n{bad} case(s) still fail after the patch")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
