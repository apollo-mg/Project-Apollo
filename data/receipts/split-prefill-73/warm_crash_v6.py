#!/usr/bin/env python3
"""V6: V5's sequence (fresh server, chat turn 1, 30 s idle, turn 2 extending it) on the daily flags PLUS
--no-vbr-prompt-cache (no idle VBR artifact publishing). Does it avoid the abort, and does turn 2 still reuse?
Launches llama-server itself over ssh (flags = run_legs.sh COMMON + -sm tensor -np 1 + the switch)."""
import json, subprocess, time
from warm_crash_repro_lib import call, ssh, write, system, tools, KW, NODE
FLAGS = ("-m '/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf' --mmproj '/mnt/models/AI_Models/Qwen 3.8/mmproj-F16.gguf' "
         "-ngl 99 -c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -np 1 -fit off -sm tensor -fa on "
         "--spec-type draft-mtp --draft-max 3 --jinja --kv-unified --chat-template-kwargs '{\"reasoning_effort\":\"medium\"}' "
         "--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 0.0 --host 0.0.0.0 --port 8080 --no-vbr-prompt-cache")
ssh("pkill -x llama-server; sleep 5")
ssh(f"mkdir -p ~/split73; setsid nohup ~/buun-llama-cpp/build_sm60_0920/bin/llama-server {FLAGS} > ~/split73/V6.log 2>&1 < /dev/null & echo $! > ~/split73/V6.pid")
for _ in range(120):
    try:
        if call(NODE, "GET", "/health", timeout=5).get("status") == "ok": break
    except Exception: pass
    time.sleep(3)
pid = ssh("cat ~/split73/V6.pid")
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
write({"variant": "V6_plain_chat_no_vbr_prompt_cache", "wait_s": 30, "turn1_prompt_n": r1.get("timings", {}).get("prompt_n"),
       "turn2_cache_n": t.get("cache_n"), "turn2_prompt_n": t.get("prompt_n"), "chat_error": err, "server": alive,
       "assert": ssh("grep -m1 GGML_ASSERT ~/split73/V6.log") if alive == "DEAD" else ""})
ssh(f"kill {pid}")
