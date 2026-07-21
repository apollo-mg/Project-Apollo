#!/usr/bin/env bash
# Did CUDA graph capture ACTUALLY happen with GGML_CUDA_FORCE_GRAPHS=1 on sm_60?
# The A/B showed no delta, but a null is only meaningful if the knob moved.
# ggml_cuda_graph_set_enabled() logs at GGML_LOG_DEBUG; production verbosity hides it.
# Relaunch once with -lv 10 and read the graph decisions directly.
set -u
R=~/buun_vbr; LOG=$R/confirm_graphs.log
log(){ echo "[$(date +%F_%T)] $*" | tee -a "$LOG"; }
pgrep -f "[b]uun_vbr/build/bin/llama-server" | while read p; do kill -9 "$p"; done; sleep 6
python3 - <<'PY'
import json,os,subprocess
argv=json.load(open(os.path.expanduser("~/buun_vbr/argv_backup.json")))
argv += ["-lv","10"]
env=dict(os.environ); env["GGML_CUDA_FORCE_GRAPHS"]="1"
out=open(os.path.expanduser("~/buun_vbr/server_confirm.log"),"w")
subprocess.Popen(argv,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,
                 stdin=subprocess.DEVNULL,env=env)
PY
log "launched with GGML_CUDA_FORCE_GRAPHS=1 and -lv 10"
for i in $(seq 1 400); do
  curl -s -m 5 http://127.0.0.1:8082/health 2>/dev/null | grep -q '"status":"ok"' && break
  sleep 5
done
log "healthy; issuing one decode to exercise the graph path"
curl -s -m 900 http://127.0.0.1:8082/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Count from one to forty in words, comma separated. Then say DONE."}],"max_tokens":3000,"temperature":0}' \
  -o /dev/null
log "=== CUDA-graph decisions in the log ==="
grep -inE "disabling CUDA graphs|CUDA graph|cuda_graph|unsupported node type|GPU architecture" \
  $R/server_confirm.log | head -20 | tee -a "$LOG"
log "=== (count of 'disabling CUDA graphs' hits: $(grep -ic 'disabling CUDA graphs' $R/server_confirm.log)) ==="
touch $R/confirm.done
