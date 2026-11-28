#!/bin/bash
# Pre-prereg smoke (no M1 item): Strata 0.2.23 / Inkling engine 0.1.70 (CUDA 12) on .73's two P100s, SQ-20 pack. Does it
# serve run_main's endpoints (/tokenize, /apply-template), honour reasoning_effort "none", and answer in M1's format?
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/inkling-strata; S=$H/raw/smoke.log; log() { echo "$* $(date '+%F %T')" >> $S; }
. $H/strata73.sh
take_73
if serve_pack SMOKE SQ-20; then
  log "served; endpoints: tokenize $(curl -s -o /dev/null -w '%{http_code}' -X POST 127.0.0.1:$TPORT/tokenize -d '{"content":"Exact Answer: UNKNOWN","with_pieces":true}') apply-template $(curl -s -o /dev/null -w '%{http_code}' -X POST 127.0.0.1:$TPORT/apply-template -d '{"messages":[{"role":"user","content":"Q"}]}') props $(curl -s -o /dev/null -w '%{http_code}' 127.0.0.1:$TPORT/props)"
  curl -s -X POST 127.0.0.1:$TPORT/apply-template -d '{"messages":[{"role":"user","content":"Q"}],"chat_template_kwargs":{"reasoning_effort":"none"}}' > $H/raw/smoke_apply_template.json
  $R/venv_cachyos/bin/python3 - $TPORT >> $H/raw/smoke.jsonl 2>&1 <<'PY'
import json, sys, time, urllib.request
port = sys.argv[1]
P = json.load(open("/mnt/TG_2TB/Projects/Apollo/data/receipts/viability/fixture_v0_beta.json"))["tier_cal"]["prompt"]
NEUTRAL = {"presence_penalty": 0, "frequency_penalty": 0, "repeat_penalty": 1, "repetition_penalty": 1, "dry_multiplier": 0}
for eff in ("none", None):
    for q in ["What is the chemical symbol for tungsten?", "In what year was the Peace of Westphalia signed?",
              "What is the atomic number of the element veridium?", "Who was the chief engineer of the Marrowby Tidal Bridge?"]:
        body = {"messages": [{"role": "user", "content": P.format(q=q)}], "temperature": 0, "max_tokens": 4096, "cache_prompt": False, **NEUTRAL}
        if eff: body["chat_template_kwargs"] = {"reasoning_effort": eff}
        t = time.time(); r = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}), timeout=900))
        m = r["choices"][0]["message"]; u = r.get("usage") or {}
        print(json.dumps({"effort": eff or "default", "q": q, "content": (m.get("content") or "")[:250], "reasoning_chars": len(m.get("reasoning_content") or ""),
                          "tokens": u.get("completion_tokens"), "finish": r["choices"][0].get("finish_reason"), "secs": round(time.time() - t, 1),
                          "tps": (r.get("timings") or {}).get("predicted_per_second")}), flush=True)
PY
  log "chat rc=$?"
else log "SMOKE pack did not serve"; fi
stop_pack; rx "cat ~/strata_launch_SMOKE.log" > $H/raw/strata_launch_SMOKE.log 2>&1; sed -i 's#/home/mark/#~/#g' $H/raw/strata_launch_SMOKE.log
give_73; log SMOKE_DONE
