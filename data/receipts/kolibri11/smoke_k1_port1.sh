#!/bin/bash
# Pre-prereg smoke: Kolibri 1 Q4_K_M on October's port 1 (Hob-forge 60d1d51cc), thinking off via enable_thinking=false,
# four fresh non-M1 questions in M1's CAL prompt (the October smoke used --reasoning off and free-form questions).
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/kolibri11; S=$H/raw/smoke.log; log() { echo "$* $(date '+%F %T')" >> $S; }
HOST=mark@10.0.0.194; IP=10.0.0.194; PORT=8096; B='~/k194/llama.cpp/build_sm60/bin'
rx() { ssh -o BatchMode=yes $HOST "$1"; }
F="-ngl 99 -sm layer -fa on -fit off -c 8192 -np 1 -ctk f16 -ctv f16 --jinja --cache-ram 0"
rx "GGML_CUDA_ALLREDUCE=internal setsid nohup $B/llama-server -m ~/AI/Models/kolibri/Kolibri-1-Q4_K_M.gguf $F --host 0.0.0.0 --port $PORT > ~/k11_server_K1port1.log 2>&1 < /dev/null & echo \$! > ~/k11_server.pid"
ok=0; for i in $(seq 300); do curl -s -m 3 $IP:$PORT/health | grep -q ok && { ok=1; break; }; rx "kill -0 \$(cat ~/k11_server.pid) 2>/dev/null" || break; sleep 2; done
log "K1port1 server healthy=$ok"
[ $ok = 1 ] && $R/venv_cachyos/bin/python3 - $IP $PORT K1port1 >> $H/raw/smoke.jsonl 2>&1 <<'PY'
import json, sys, time, urllib.request
ip, port, tag = sys.argv[1:4]
P = json.load(open("/mnt/TG_2TB/Projects/Apollo/data/receipts/viability/fixture_v0_beta.json"))["tier_cal"]["prompt"]
for q in ["What is the chemical symbol for tungsten?", "In what year was the Peace of Westphalia signed?",
          "What is the atomic number of the element veridium?", "Who was the chief engineer of the Marrowby Tidal Bridge?"]:
    body = {"messages": [{"role": "user", "content": P.format(q=q)}], "temperature": 0, "max_tokens": 1024, "cache_prompt": False,
            "chat_template_kwargs": {"enable_thinking": False}}
    t = time.time(); r = json.load(urllib.request.urlopen(urllib.request.Request(f"http://{ip}:{port}/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}), timeout=900))
    m = r["choices"][0]["message"]
    print(json.dumps({"tag": tag, "q": q, "content": (m.get("content") or "")[:300], "reasoning_chars": len(m.get("reasoning_content") or ""),
                      "tokens": r["usage"]["completion_tokens"], "finish": r["choices"][0]["finish_reason"], "secs": round(time.time() - t, 1),
                      "tps": (r.get("timings") or {}).get("predicted_per_second")}, ensure_ascii=False), flush=True)
PY
log "K1port1 chat rc=$?"
rx "kill \$(cat ~/k11_server.pid) 2>/dev/null"; sleep 5; scp -q $HOST:k11_server_K1port1.log $H/raw/
log SMOKE_K1_DONE
