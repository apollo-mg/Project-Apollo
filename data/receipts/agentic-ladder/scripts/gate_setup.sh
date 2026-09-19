#!/usr/bin/env bash
# P-A0 gate setup: serve ONE ladder arm on .73:8084 and stand up an isolated Hermes gateway.
#
# Uses port 8084 and gateway 8643 deliberately: Mark's PRODUCTION gateway is on 8642 and his
# daily driver serves :8080 through the wake proxy. Neither is touched by name here -- but the
# daily driver must be stopped anyway, because .73 has 32 GB of VRAM and it holds ~26.
#
# -sm layer, NOT tensor. Tensor-split asserts every split dimension is divisible by the device
# count (ggml-backend-meta.cpp:1086 GGML_ASSERT(split_state.ne[j] % div == 0)), and the ternary
# packing does not satisfy it -- the model loads into VRAM and then aborts. The ladder ran these
# exact files all day with -sm layer. See also the tensor-split deny list (upstream #27941).
#
# reasoning_effort=medium is LOAD-BEARING, not cosmetic. On Qwen3.8 it is a PROMPT EDIT (AFM-23);
# unset resolves to xhigh, ~5.85x the tokens, and destabilised long generations in prior runs --
# i.e. it would manufacture the exact runaway this gate exists to screen for.
set -u
ARM="${1:?usage: gate_setup.sh <arm-name> <gguf-path-on-.73>}"
GGUF="${2:?}"
# BINARY MUST MATCH THE CODEC. buun cannot read GGML types 142/143 -- it fails with
# "gguf_init_from_reader: failed to read tensor info", which reads like a corrupt file rather
# than an unsupported type. Ternary arms need the PrismML fork; stock GGUF arms use buun,
# the build that produced ref.kld.
case "$GGUF" in
  *Ternary-Bonsai*|*PTQ1_0*|*PQ2_0*) BIN=/home/mark/prism_llama_cpp/build_sm60/bin/llama-server ;;
  *)                                 BIN=/home/mark/buun-sm60-qual/build_sm60qual/bin/llama-server ;;
esac
echo "arm $ARM -> binary $BIN"
A=/mnt/TG_2TB/Projects/Apollo/argus
LOG=/mnt/TG_2TB/Projects/Apollo/data/receipts/agentic-ladder/logs
mkdir -p "$LOG"

echo "[$(date +%H:%M:%S)] stopping wake proxy so it cannot restart the daily driver"
systemctl --user stop apollo-wake-proxy

echo "[$(date +%H:%M:%S)] freeing VRAM on .73 (identify holder from timeout 10 nvidia-smi, never a pattern)"
ssh -n -o BatchMode=yes mark@10.0.0.73 'set -u
P=$(timeout 10 nvidia-smi --query-compute-apps=pid --format=csv,noheader | sort -u | head -1)
if [ -n "$P" ]; then
  CMD=$(tr "\0" " " < /proc/$P/cmdline)
  case "$CMD" in *llama-server*) kill -TERM "$P"; echo "  stopped llama-server pid $P";;
                 *) echo "  REFUSING: pid $P is not llama-server"; exit 1;; esac
  # The drain check must NOT be built out of nvidia-smi alone: on 2026-09-19 nvidia-smi hung,
  # and a check made of the failed component became another hung process instead of an alarm.
  # Primary signal is the PROCESS being gone; nvidia-smi is corroboration and is bounded, and
  # an unanswerable nvidia-smi is its own distinct, loud failure.
  for i in $(seq 1 60); do sleep 2
    kill -0 "$P" 2>/dev/null || { echo "  process $P gone after $((i*2))s"; break; }
  done
  if kill -0 "$P" 2>/dev/null; then echo "  WARNING: pid $P still alive after 120s"; fi
  if HI=$(timeout 10 nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | sort -rn | head -1); then
    echo "  VRAM high-water now ${HI:-unknown} MiB"
  else
    echo "  *** GPU NOT ANSWERING: nvidia-smi timed out. ABORTING rather than polling it again. ***"
    exit 1
  fi
fi
timeout 10 nvidia-smi --query-gpu=index,memory.used --format=csv,noheader'

echo "[$(date +%H:%M:%S)] starting $ARM on .73:8084 at temp 0"
ssh -n -o BatchMode=yes mark@10.0.0.73 "setsid nohup $BIN \
  -m '$GGUF' -ngl 99 -c 65536 -np 1 -sm layer -fit off -ctk f16 -ctv f16 -fa on --jinja \
  --chat-template-kwargs '{\"reasoning_effort\":\"medium\"}' \
  --temp 0 --top-k 1 --top-p 1.0 --min-p 0.0 --repeat-penalty 1.0 --presence-penalty 0.0 \
  --host 0.0.0.0 --port 8084 > ~/argus_${ARM}_8084.log 2>&1 < /dev/null & echo \$! > ~/argus_${ARM}.pid
  echo \"  pid \$(cat ~/argus_${ARM}.pid)\"
  for i in \$(seq 1 90); do
    [ \"\$(curl -s -o /dev/null -w %{http_code} -m 3 http://127.0.0.1:8084/health)\" = '200' ] && { echo \"  READY after \$((i*5))s\"; exit 0; }
    kill -0 \$(cat ~/argus_${ARM}.pid) 2>/dev/null || { echo '  DIED during load:'; grep -iE 'error|failed' ~/argus_${ARM}_8084.log | head -3; exit 1; }
    sleep 5
  done; echo '  TIMEOUT waiting for health'; exit 1" || { echo "MODEL FAILED TO SERVE"; exit 1; }

echo "[$(date +%H:%M:%S)] pointing the ISOLATED agent-home at .73:8084 (backing up first)"
cp -n "$A/agent-home/config.yaml" "$A/agent-home/config.yaml.orig" 2>/dev/null || true
sed -i 's|^\( *base_url: \).*|\1http://10.0.0.73:8084/v1|' "$A/agent-home/config.yaml"
sed -i "s|^\( *default: \).*\.gguf|\1$GGUF|" "$A/agent-home/config.yaml"
grep -nE "base_url|default:" "$A/agent-home/config.yaml" | head -3

echo "[$(date +%H:%M:%S)] starting isolated gateway on 8643 (Mark's production 8642 untouched)"
cd /mnt/TG_2TB/AI/hermes-go
HERMES_HOME=$A/agent-home API_SERVER_KEY=argus-local-test-key-0123456789 \
  API_SERVER_PORT=8643 HERMES_BUNDLED_SKILLS=$A/agent-home/no-bundled-skills \
  setsid nohup .venv/bin/python scripts/hermes-gateway > "$LOG/gateway_${ARM}.log" 2>&1 < /dev/null &
echo $! > /tmp/argus_gateway.pid
echo "  gateway pid $(cat /tmp/argus_gateway.pid)"
for i in $(seq 1 60); do
  sleep 2
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 3 -H "Authorization: Bearer argus-local-test-key-0123456789" http://127.0.0.1:8643/api/sessions 2>/dev/null)
  case "$code" in 200|401|405) echo "  gateway UP after $((i*2))s (http $code)"; exit 0;; esac
  kill -0 "$(cat /tmp/argus_gateway.pid)" 2>/dev/null || { echo "  gateway DIED:"; tail -5 "$LOG/gateway_${ARM}.log"; exit 1; }
done
echo "  gateway TIMEOUT"; tail -5 "$LOG/gateway_${ARM}.log"; exit 1
