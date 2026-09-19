#!/usr/bin/env bash
# The agentic panel on .194: four arms, ONE pass each (P-A0 proved temp-0 determinism),
# ONE binary for every arm, one variable -- the codec.
#
# ALL ARMS USE THE PRISM BINARY. It is a llama.cpp fork, so it serves stock GGUF types as well
# as 142/143. Using one binary removes the cross-binary confound entirely, which is the agentic
# equivalent of the fidelity ladder's C-XBIN control -- but by construction rather than by a
# control arm. Verified empirically before the panel runs, not assumed.
#
# GGML_CUDA_ALLREDUCE=internal is MANDATORY on .194. Unset, the default is NCCL, which ABORTS on
# this box (allreduce-internal-inert-on-pascal). It is inert on sm_60 either way, so setting it
# costs nothing and not setting it loses the run.
#
# MTP is NOT used on any arm. Bonsai ships no draft head, so enabling it elsewhere would compare
# codecs at different speculative-decoding settings.
set -u
BIN=/home/mark/prism_llama_cpp/build_sm60/bin/llama-server
A=/mnt/TG_2TB/Projects/Apollo/argus
R=/mnt/TG_2TB/Projects/Apollo/data/receipts/agentic-ladder
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
mkdir -p "$R/logs"

# The isolated gateway runs on the DESKTOP and talks to .194:8084. agent-home/config.yaml
# already points there by default, so no config edit is needed -- and Mark's production gateway
# on 8642 is untouched. The fake-google fixture also lives on the desktop, so all four arms see
# the SAME world, seed 806c5016..., already rebased and frozen for the gate.
#
# FREE CROSS-MACHINE CHECK: P-BPQ2 is the same model, same seed and same scenarios as the P-A0
# gate arm, which ran on .73 with a different prism build. If it reproduces 9/15 here, that is an
# independent replication across hardware and build; if it does not, one of those is a variable
# we did not control and we find out before interpreting anything.
if ! ss -lnt 2>/dev/null | grep -q ':8643'; then
  echo "starting isolated gateway on 8643" | tee -a "$R/logs/panel.log"
  ( cd /mnt/TG_2TB/AI/hermes-go && HERMES_HOME=$A/agent-home       API_SERVER_KEY=argus-local-test-key-0123456789 API_SERVER_PORT=8643       HERMES_BUNDLED_SKILLS=$A/agent-home/no-bundled-skills       setsid nohup .venv/bin/python scripts/hermes-gateway > "$R/logs/gateway_panel.log" 2>&1 < /dev/null &       echo $! > /tmp/panel_gateway.pid )
  for i in $(seq 1 60); do
    sleep 2
    c=$(curl -s -o /dev/null -w '%{http_code}' -m 3 -H "Authorization: Bearer argus-local-test-key-0123456789" http://127.0.0.1:8643/api/sessions 2>/dev/null)
    case "$c" in 200|401|405) echo "  gateway UP ($c)" | tee -a "$R/logs/panel.log"; break;; esac
  done
fi

declare -A ARMS=(
  [P-BASE]=/home/mark/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf
  [P-GIQ2]=/home/mark/AI/Models/ladder/Qwen3.8-27B-GSQ-RCO-IQ2_XS-mtp.gguf
  [P-AIQ3S]=/home/mark/AI/Models/ladder/Qwen3.8-27B-AD-IQ3_S-IQ3_XXS.gguf
  [P-BPQ2]=/home/mark/AI/Models/ladder/Ternary-Bonsai-2-27B-PQ2_0.gguf
)
ORDER=(P-BASE P-GIQ2 P-AIQ3S P-BPQ2)

for arm in "${ORDER[@]}"; do
  M="${ARMS[$arm]}"
  echo "######## $arm  $(date -Iseconds)" | tee -a "$R/logs/panel.log"

  # fresh server per arm -- server-uptime-is-a-variable
  ssh -n -o BatchMode=yes mark@10.0.0.194 "pkill -x llama-server 2>/dev/null; sleep 4
    setsid nohup env GGML_CUDA_ALLREDUCE=internal $BIN -m '$M' \
      -ngl 99 -c 65536 -np 1 -sm layer -fit off -ctk f16 -ctv f16 -fa on --jinja \
      --chat-template-kwargs '{\"reasoning_effort\":\"medium\"}' \
      --temp 0 --top-k 1 --top-p 1.0 --min-p 0.0 --repeat-penalty 1.0 --presence-penalty 0.0 \
      --host 0.0.0.0 --port 8084 > ~/argus_${arm}_8084.log 2>&1 < /dev/null & echo \$! > ~/argus_${arm}.pid
    for i in \$(seq 1 120); do
      [ \"\$(timeout 3 curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8084/health)\" = '200' ] && { echo READY_\$((i*5))s; exit 0; }
      kill -0 \$(cat ~/argus_${arm}.pid) 2>/dev/null || { echo DIED; grep -iE 'error|failed|assert' ~/argus_${arm}_8084.log | head -3; exit 1; }
      sleep 5
    done; echo LOAD_TIMEOUT; exit 1" | tee -a "$R/logs/panel.log" || { echo "$arm FAILED TO SERVE" | tee -a "$R/logs/panel.log"; continue; }

  cd "$A"
  rm -f "runs/panel_${arm}.jsonl"
  timeout 5400 $PY driver.py --transport gateway --base http://127.0.0.1:8643 \
    --fake-root "$A/fake-google" --scenarios scenarios_v1_pool_gate.json \
    --out "runs/panel_${arm}.jsonl" --events "runs/live_panel_${arm}.jsonl" \
    --timeout 900 >> "$R/logs/panel_${arm}.log" 2>&1
  echo "   $arm rc=$? rows=$(wc -l < runs/panel_${arm}.jsonl 2>/dev/null || echo 0)" | tee -a "$R/logs/panel.log"
done
ssh -n -o BatchMode=yes mark@10.0.0.194 'pkill -x llama-server 2>/dev/null; true'
echo "######## PANEL DONE $(date -Iseconds)" | tee -a "$R/logs/panel.log"
