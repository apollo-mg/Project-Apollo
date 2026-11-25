#!/bin/bash
# 11-24 22:10: -ts 1,3 added. inkling2_loop sets n_layer_all to 48 cache slots (24 physical + 2 x 12 loop) and the layer split is computed over slots, so an even split puts all 24 physical layers on CUDA0 (22.8 GB, OOM); 1,3 puts physical 0-12 on CUDA0, 13-23 + output on CUDA1.
# Pre-prereg smoke for Inkling-2-Mini on .73 (no M1 item is asked): does mainline 33aeb17f8 load the looped model on two
# P100s, does the server split thinking from the answer, how many tokens do reasoning_effort "none" and the default spend,
# and is wikitext perplexity free of gross breakage. Pauses the wake proxy and restores it.
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/inkling-mini; S=$H/raw/smoke.log; log() { echo "$* $(date '+%F %T')" >> $S; }
HOST=mark@10.0.0.73; IP=10.0.0.73; PORT=8190; BIN='~/llama.cpp-33aeb17f/build_sm60/bin'; M=/mnt/models/inkling/Inkling-2-Mini-AD-Q6_K.gguf
rx() { ssh -o BatchMode=yes $HOST "$1"; }
curl -s -m 120 -X POST 127.0.0.1:8099/wake > /dev/null; sleep 5
systemctl --user stop apollo-wake-proxy; log "wake proxy stopped"
rx "setsid nohup sleep 7200 > /dev/null 2>&1 < /dev/null & echo \$! > /tmp/apollo-busy.inkling"
P=$(rx 'pgrep -x llama-server'); [ -n "$P" ] && rx "kill $P"
for i in $(seq 60); do u=$(rx "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1"); [ "${u:-99999}" -lt 500 ] && break; sleep 5; done
rx "mkdir -p ~/inkling; CUDA_VISIBLE_DEVICES=0,1 GGML_CUDA_ALLREDUCE=internal setsid nohup $BIN/llama-server -m $M -ngl 99 -sm layer -fit off -ts 1,3 -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0 --host 0.0.0.0 --port $PORT > ~/inkling/server_smoke.log 2>&1 < /dev/null & echo \$! > ~/inkling/server.pid"
ok=0; for i in $(seq 300); do curl -s -m 3 $IP:$PORT/health | grep -q ok && { ok=1; break; }; sleep 2; done; log "server healthy=$ok"
if [ $ok = 1 ]; then
  $R/venv_cachyos/bin/python3 - $IP $PORT >> $H/raw/smoke_chat.txt 2>&1 <<'PY'
import json, sys, time, urllib.request
ip, port = sys.argv[1], sys.argv[2]
qs = ["What is the capital of Australia? Answer in one short sentence.", "Who wrote the novel Pride and Prejudice?",
      "What is 17 times 23? Give just the number.", "What is the capital of the fictional country Zembrovia?",
      "In what year was the University of Pula founded? If you do not know, say UNKNOWN."]
for eff in ("none", None):
    for q in qs:
        body = {"messages": [{"role": "user", "content": q}], "temperature": 0, "max_tokens": 2048}
        if eff: body["chat_template_kwargs"] = {"reasoning_effort": eff}
        t = time.time()
        r = json.load(urllib.request.urlopen(urllib.request.Request(f"http://{ip}:{port}/v1/chat/completions",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}), timeout=900))
        m = r["choices"][0]["message"]; u = r.get("usage", {})
        print(json.dumps({"effort": eff or "default(0.9)", "q": q[:50], "content": (m.get("content") or "")[:200],
                          "reasoning_chars": len(m.get("reasoning_content") or ""), "reasoning_head": (m.get("reasoning_content") or "")[:120],
                          "completion_tokens": u.get("completion_tokens"), "finish": r["choices"][0].get("finish_reason"),
                          "secs": round(time.time() - t, 1)}), flush=True)
PY
  log "chat smoke rc=$?"
fi
rx "kill \$(cat ~/inkling/server.pid) 2>/dev/null"; sleep 5
scp -q $R/../../AI/kld/wikitext-2-raw/wiki.test.raw $HOST:inkling/ 2>/dev/null || scp -q /mnt/TG_2TB/AI/kld/wikitext-2-raw/wiki.test.raw $HOST:inkling/
rx "CUDA_VISIBLE_DEVICES=0,1 GGML_CUDA_ALLREDUCE=internal $BIN/llama-perplexity -m $M -f ~/inkling/wiki.test.raw -c 512 --chunks 10 -ngl 99 -sm layer -fit off -ts 1,3 > ~/inkling/ppl_smoke.log 2>&1"
log "ppl rc=$? $(rx 'grep -o "Final estimate: PPL = [0-9.]*" ~/inkling/ppl_smoke.log')"
scp -q "$HOST:inkling/server_smoke.log" "$HOST:inkling/ppl_smoke.log" $H/raw/
rx "kill \$(cat /tmp/apollo-busy.inkling) 2>/dev/null; rm -f /tmp/apollo-busy.inkling"
systemctl --user start apollo-wake-proxy; log "wake proxy started; SMOKE_DONE"
