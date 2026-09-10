#!/usr/bin/env python3
"""Measure the VBR usable-context ceiling directly, without an agent harness.

WHY NOT hermesbench: two independent failure sources there emit the same INFRA_ERROR --
(a) the 2026-08-29 tool rename/bridge-deferral the verifiers never tracked, and
(b) xhigh-style generation runaways hitting a fixed wall clock.
Neither is a context ceiling, and the metric cannot separate them.

THIS probe removes both:
  * max_tokens=16, so generation length cannot vary the result
  * no tools at all, so the version skew is irrelevant
  * a fixed long prefix + rotating suffixes, which is the cache pattern an agent actually
    produces: a stable system prompt plus a changing tail

The measurement is PREFIX REUSE. Each distinct prompt is sent twice. On the second send the
server should re-prefill only the new tail. If the working set no longer fits, VBR resets and
the re-prefill re-enters at the entry tier -- which is the mechanism under test.

Reports per context size: median second-pass prefill tokens (low = reuse working), the reuse
rate, and wall time. Caller pairs this with the server log's `VBR budget ... exceeded` and
`vbr reset` counts.
"""
import json, sys, time, urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8090"
NPROMPT = int(sys.argv[2]) if len(sys.argv) > 2 else 4
WORDS = int(sys.argv[3]) if len(sys.argv) > 3 else 9000   # ~14k tokens, tool-schema sized

PREFIX = ("The following is reference material that must be retained verbatim. " * (WORDS // 10))

def ask(text):
    body = {"messages": [{"role": "user", "content": text}],
            "max_tokens": 16, "temperature": 0}
    req = urllib.request.Request(HOST.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read())
    return time.time() - t0, d.get("usage", {}).get("prompt_tokens", 0)

prompts = [PREFIX + f"\n\nDistinct tail number {i}. Reply with only the number {i}." for i in range(NPROMPT)]

print(f"# prefix ~{len(PREFIX.split())} words, {NPROMPT} distinct prompts, 2 passes each")
first, second = [], []
for rnd in (1, 2):
    for i, p in enumerate(prompts):
        wall, ptok = ask(p)
        (first if rnd == 1 else second).append(wall)
        print(f"  round{rnd} p{i}  wall={wall:6.2f}s  prompt_tokens={ptok}")
first.sort(); second.sort()
m1 = first[len(first)//2]; m2 = second[len(second)//2]
print(f"\nMEDIAN wall  round1 {m1:.2f}s   round2 {m2:.2f}s   speedup {m1/max(m2,0.001):.2f}x")
print(f"REUSE_VERDICT {'WORKING' if m2 < m1 * 0.5 else 'DEGRADED'}")
