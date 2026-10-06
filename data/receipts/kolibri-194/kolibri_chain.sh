#!/usr/bin/env bash
# PREREG_KOLIBRI_194 arms on .194 (detached): sha gate -> K_load + K_sane -> K_ppl -> K_speed (run194.sh).
cd ~/sbench; OUT=~/sbench/runs_kolibri; mkdir -p $OUT; L=$OUT/run.log
log() { echo "$(date '+%F %T') $*" >> $L; }
for i in $(seq 1 360); do grep -q -E 'KOLIBRI_GGUF_(OK|FAIL)' ~/k194/prep.log && break; sleep 10; done
for i in $(seq 1 360); do grep -q -E "All set|\[x\]|Traceback" ~/strata-setup-iq4.log && break; sleep 10; done
log "strata iq4 setup ended (or 60 min timeout): $(tail -c 300 ~/strata-setup-iq4.log | tr '\r\n' '  ' | cut -c1-200)"
grep -q KOLIBRI_GGUF_OK ~/k194/prep.log || { log "sha gate FAILED: $(tail -3 ~/k194/prep.log | tr '\n' ' ')"; exit 1; }
log "sha gate ok: $(grep -h 'Kolibri-1-Q4_K_M.gguf: ' ~/k194/prep.log)"
BIN=~/k194/llama.cpp/build_sm60/bin; M=~/AI/Models/kolibri/Kolibri-1-Q4_K_M.gguf
GGML_CUDA_ALLREDUCE=internal $BIN/llama-server -m $M -ngl 99 -sm layer -fa on -fit off -c 8192 -np 1 -ctk f16 -ctv f16 --jinja --reasoning off --host 127.0.0.1 --port 8096 > $OUT/server_sane.log 2>&1 & SP=$!
up=0; for i in $(seq 1 900); do kill -0 $SP 2>/dev/null || break; curl -sf -m 2 localhost:8096/health >/dev/null && { up=1; break; }; sleep 1; done
log "K_load: up=$up; $(grep -o -m1 'offloaded [0-9]*/[0-9]* layers to GPU' $OUT/server_sane.log); VRAM $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr '\n' ' ')MiB"
if [ $up = 1 ]; then
  curl -s localhost:8096/props > $OUT/props.json
  python3 - $OUT <<'PY' >> $L 2>&1
import json, sys, urllib.request
out = sys.argv[1]
p = json.load(open(out + "/props.json")); t = p.get("chat_template") or ""
print("K_load: model_path", p.get("model_path"), "| template has enable_thinking:", "enable_thinking" in t, "| <think> in template:", "think" in t)
qs = ["What is 2+2? Answer with just the number.", "Was ist die Hauptstadt von Deutschland? Antworte in einem Satz.", "Define photosynthesis in one sentence."]
res = []
for q in qs:
    body = {"messages": [{"role": "user", "content": q}], "max_tokens": 128, "temperature": 0}
    r = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8096/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=600))
    m = r["choices"][0]["message"]; res.append({"q": q, "content": m.get("content"), "reasoning_chars": len(m.get("reasoning_content") or ""), "finish": r["choices"][0].get("finish_reason")})
json.dump(res, open(out + "/sane.json", "w"), indent=1, ensure_ascii=False)
for x in res: print("K_sane:", repr((x["content"] or "")[:160]), "| reasoning chars", x["reasoning_chars"], "| finish", x["finish"])
PY
fi
kill $SP; for i in $(seq 1 60); do kill -0 $SP 2>/dev/null || break; sleep 1; done
GGML_CUDA_ALLREDUCE=internal $BIN/llama-perplexity -m $M -ngl 99 -sm layer -fa on -fit off -c 512 -b 512 --chunks 16 -f ~/wikitext-2-raw/wiki.test.raw > $OUT/ppl.txt 2>&1
log "K_ppl: rc=$? $(grep -E 'Final estimate' $OUT/ppl.txt | tail -1)"
export LLAMA_BIN=$BIN/llama-server LLAMA_MODEL=$M HFID=Hob-forge/Kolibri-1-GGUF QUANT=Q4_K_M
./run194.sh llama K_speed_r $PWD/canonical_reasoning-v1.txt "-ngl 99 -sm layer -fa on -fit off -lv 4"
./run194.sh llama K_speed_c $PWD/canonical_code-v1.txt "-ngl 99 -sm layer -fa on -fit off -lv 4"
grep -E 'K_speed' runs/run.log >> $L
log KOLIBRI_DONE
