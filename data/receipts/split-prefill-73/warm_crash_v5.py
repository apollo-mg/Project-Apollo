#!/usr/bin/env python3
"""V5 for warm_crash_repro.py: does ORDINARY chat hit the same abort? Fresh server; chat turn 1 (head + question A);
wait 30 s (idle capture publishes); turn 2 = turn 1 + assistant reply + question B. Appends raw/warm_crash_repro.jsonl."""
import json, time
from warm_crash_repro_lib import call, ssh, write, system, tools, KW, PROXY, NODE

ssh("pkill -x llama-server; sleep 5")
t0 = time.time(); call(PROXY, "GET", "/props"); load_s = round(time.time() - t0, 1)
pid = ssh("pgrep -x llama-server")
m = [{"role": "system", "content": system}, {"role": "user", "content": "Name one claim it makes, briefly."}]
r1 = call(NODE, "POST", "/v1/chat/completions", {"messages": m, "tools": tools, "max_tokens": 24, "temperature": 0, **KW})
reply = r1["choices"][0]["message"].get("content") or ""
time.sleep(30)
m += [{"role": "assistant", "content": reply}, {"role": "user", "content": "Why might that be wrong? One line."}]
err, t = None, {}
try:
    t = call(NODE, "POST", "/v1/chat/completions", {"messages": m, "tools": tools, "max_tokens": 16, "temperature": 0, **KW}).get("timings", {})
except Exception as e:
    err = repr(e)
time.sleep(3)
alive = ssh(f"kill -0 {pid} 2>/dev/null && echo alive || echo DEAD")
write({"variant": "V5_plain_chat", "wait_s": 30, "load_s": load_s, "turn1_prompt_n": r1.get("timings", {}).get("prompt_n"),
       "turn2_cache_n": t.get("cache_n"), "turn2_prompt_n": t.get("prompt_n"), "chat_error": err, "server": alive,
       "assert": ssh("grep -m1 GGML_ASSERT ~/wake_proxy_server.log") if alive == "DEAD" else ""})
if alive == "DEAD":
    ssh("cp ~/wake_proxy_server.log ~/crash_prewarm_V5.log")
