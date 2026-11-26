#!/bin/bash
# Pre-prereg smoke for the Olmo 3 7B Think ladder (Think-SFT, Think-DPO, Think) on the desktop. No M1 item is asked: six
# fresh questions (chemistry, history, arithmetic, two invented) in M1's CAL prompt. Checks: does the server split the
# reasoning from the answer (the template opens <think> itself), does the model end its turn, how many tokens it spends
# (16,384 cap here, to see natural lengths), and whether the answer follows the format. Usage: smoke_think.sh NAME...
# 11-25 21:20: records the content tail and the </think> count (the first Think-SFT pass kept only the first 300 characters).
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/olmo3-ladder; S=$H/raw/smoke_think.log; log() { echo "$* $(date '+%F %T')" >> $S; }
BIN=$R/engines/rocm10/up_33aeb17f/build_rocm/bin; G=/mnt/HDD/Models/olmo3-7b-gguf; PORT=8096
FLAGS=(-ngl 99 -c 32768 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0)
for N in "$@"; do
  M=$G/$N-Q8_0.gguf
  $R/tools/rocm101arch.sh $BIN/llama-server -m $M "${FLAGS[@]}" --host 127.0.0.1 --port $PORT > $H/raw/server_smoke_$N.log 2>&1 &
  SP=$!; ok=0; for i in $(seq 150); do curl -s 127.0.0.1:$PORT/health | grep -q ok && { ok=1; break; }; kill -0 $SP 2>/dev/null || break; sleep 2; done
  log "$N server healthy=$ok"
  if [ $ok = 1 ]; then
    $R/venv_cachyos/bin/python3 - $PORT $N >> $H/raw/smoke_think.jsonl 2>&1 <<'PY'
import json, sys, time, urllib.request
port, name = sys.argv[1], sys.argv[2]
FIX = json.load(open("/mnt/TG_2TB/Projects/Apollo/data/receipts/viability/fixture_v0_beta.json")); PROMPT = FIX["tier_cal"]["prompt"]
qs = ["What is the chemical symbol for tungsten?", "In what year was the Peace of Westphalia signed?",
      "Which chemical element has atomic number 72?", "What is 17 times 23?",
      "What is the atomic number of the element veridium?", "Who was the chief engineer of the Marrowby Tidal Bridge?"]
for q in qs:
    body = {"messages": [{"role": "user", "content": PROMPT.format(q=q)}], "temperature": 0, "max_tokens": 16384, "cache_prompt": False}
    t = time.time()
    r = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}), timeout=3600))
    m = r["choices"][0]["message"]; u = r.get("usage", {}); rc = m.get("reasoning_content") or ""
    c = m.get("content") or ""
    print(json.dumps({"model": name, "q": q, "content": c[:300], "content_tail": c[-200:], "close_think": c.count("</think>"), "reasoning_chars": len(rc),
                      "reasoning_head": rc[:100], "reasoning_tail": rc[-100:], "completion_tokens": u.get("completion_tokens"),
                      "finish": r["choices"][0].get("finish_reason"), "secs": round(time.time() - t, 1),
                      "tps": (r.get("timings") or {}).get("predicted_per_second")}), flush=True)
PY
    log "$N chat smoke rc=$?"
  fi
  kill $SP 2>/dev/null; wait $SP 2>/dev/null
done
log SMOKE_DONE
