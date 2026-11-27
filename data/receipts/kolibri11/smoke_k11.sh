#!/bin/bash
# Pre-prereg checks for Kolibri 1.1 on .194 (4x P100, PR #32891 5f4d22289 build_sm60). No M1 item is asked.
#  1. test-backend-ops on CUDA0 for the ops the PR adds or changes (ROUND_NVFP4, the lightning indexer, flash attention).
#  2. Kolibri 1.1 Q4_K_M: load, four fresh questions with thinking off in M1's CAL prompt, wikitext PPL (16 x 512).
#  3. Kolibri 1 Q4_K_M (Hob-forge, October): does this build load it, and is PPL at 512 near October's 28.4 (port 1)?
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/kolibri11; S=$H/raw/smoke.log; log() { echo "$* $(date '+%F %T')" >> $S; }
HOST=mark@10.0.0.194; IP=10.0.0.194; PORT=8096; B='~/llama.cpp-pr32891/build_sm60/bin'; MD='~/AI/Models/kolibri'
rx() { ssh -o BatchMode=yes $HOST "$1"; }
F="-ngl 99 -sm layer -fa on -fit off -c 8192 -np 1 -ctk f16 -ctv f16 --jinja --cache-ram 0"
rx "cd ~/AI/Models/kolibri; $B/test-backend-ops -b CUDA0 -o ROUND_NVFP4 > ~/k11_ops_round.log 2>&1; $B/test-backend-ops -b CUDA0 -o LIGHTNING_INDEXER > ~/k11_ops_li.log 2>&1; $B/test-backend-ops -b CUDA0 -o FLASH_ATTN_EXT > ~/k11_ops_fa.log 2>&1; true"
for t in round li fa; do log "ops $t: $(rx "grep -E 'tests passed|Backend CUDA0|FAIL' ~/k11_ops_$t.log | tail -3 | tr '\n' ' '")"; done
for spec in "K11|Kolibri-1.1-Q4_K_M.gguf" "K1|Kolibri-1-Q4_K_M.gguf"; do
  IFS='|' read -r TAG FILE <<< "$spec"
  rx "cd ~/AI/Models/kolibri; GGML_CUDA_ALLREDUCE=internal setsid nohup $B/llama-server -m $MD/$FILE $F --host 0.0.0.0 --port $PORT > ~/k11_server_$TAG.log 2>&1 < /dev/null & echo \$! > ~/k11_server.pid"
  ok=0; for i in $(seq 300); do curl -s -m 3 $IP:$PORT/health | grep -q ok && { ok=1; break; }; rx "kill -0 \$(cat ~/k11_server.pid) 2>/dev/null" || break; sleep 2; done
  log "$TAG server healthy=$ok; VRAM $(rx "nvidia-smi --query-gpu=memory.used,clocks.sm --format=csv,noheader | tr '\n' ' '")"
  if [ $ok = 1 ]; then
    $R/venv_cachyos/bin/python3 - $IP $PORT $TAG >> $H/raw/smoke.jsonl 2>&1 <<'PY'
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
    log "$TAG chat rc=$?"
  fi
  rx "kill \$(cat ~/k11_server.pid) 2>/dev/null"; sleep 8
  rx "GGML_CUDA_ALLREDUCE=internal $B/llama-perplexity -m $MD/$FILE -ngl 99 -sm layer -fa on -fit off -c 512 -b 512 --chunks 16 -f ~/wikitext-2-raw/wiki.test.raw > ~/k11_ppl_$TAG.log 2>&1"
  log "$TAG ppl rc=$? $(rx "grep -o 'Final estimate: PPL = [0-9.]* +/- [0-9.]*' ~/k11_ppl_$TAG.log")"
done
scp -q "$HOST:k11_*.log" $H/raw/
log SMOKE_DONE
