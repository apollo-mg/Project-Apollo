#!/bin/bash
# Pre-prereg smoke: does the BONB9 binary (prism 9a9394a89, ROCm 7.2.4 runtime) load Bonsai 2.5 and answer coherently with
# thinking off? Four fresh non-M1 questions in M1's CAL prompt.
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/bonsai25; BIN=$R/engines/prism_sep/build_hip/bin/llama-server; PORT=8097
M=/mnt/HDD/Models/bonsai-2.5-27b/Ternary-Bonsai-2.5-27B-PQ2_0.gguf
$R/tools/rocm724.sh $BIN -m $M -ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 127.0.0.1 --port $PORT > $H/raw/server_smoke.log 2>&1 &
SP=$!; ok=0; for i in $(seq 150); do curl -s 127.0.0.1:$PORT/health | grep -q ok && { ok=1; break; }; kill -0 $SP 2>/dev/null || break; sleep 2; done
echo "healthy=$ok $(date '+%F %T')" > $H/raw/smoke.log
[ $ok = 1 ] && $R/venv_cachyos/bin/python3 - $PORT >> $H/raw/smoke.jsonl <<'PY'
import json, sys, time, urllib.request
port = sys.argv[1]
P = json.load(open("/mnt/TG_2TB/Projects/Apollo/data/receipts/viability/fixture_v0_beta.json"))["tier_cal"]["prompt"]
for q in ["What is the chemical symbol for tungsten?", "In what year was the Peace of Westphalia signed?",
          "What is the atomic number of the element veridium?", "Who was the chief engineer of the Marrowby Tidal Bridge?"]:
    body = {"messages": [{"role": "user", "content": P.format(q=q)}], "temperature": 0, "max_tokens": 1024, "cache_prompt": False,
            "chat_template_kwargs": {"enable_thinking": False}}
    t = time.time(); r = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}), timeout=600))
    m = r["choices"][0]["message"]
    print(json.dumps({"q": q, "content": (m.get("content") or "")[:300], "reasoning_chars": len(m.get("reasoning_content") or ""),
                      "tokens": r["usage"]["completion_tokens"], "finish": r["choices"][0]["finish_reason"], "secs": round(time.time() - t, 1),
                      "tps": (r.get("timings") or {}).get("predicted_per_second")}), flush=True)
PY
echo "rc=$? $(date '+%F %T')" >> $H/raw/smoke.log
kill $SP; wait $SP 2>/dev/null
