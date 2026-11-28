# Shared helpers for the Strata Inkling runs on .73 (sourced). Strata serves on .73's loopback only; the desktop reaches it
# through an ssh tunnel (127.0.0.1:18080 -> .73 127.0.0.1:8085). Launch flags fixed here for every arm.
HOST=mark@10.0.0.73; ST='~/.local/bin/strata'; TPORT=18080
LAUNCH="--family inkling-2-mini --context 32k --vision off --parallel 1 --tune skip --access local --port 8085 --gpu 0,1 --kv fp16 --draft off --drafting off --yes --no-tui"
rx() { ssh -o BatchMode=yes $HOST "$1"; }
take_73() {   # wake, pause the proxy, lock, stop the daily server, wait for free VRAM
  curl -s -m 120 -X POST 127.0.0.1:8099/wake > /dev/null; sleep 3
  systemctl --user stop apollo-wake-proxy; log "wake proxy stopped"
  rx "setsid nohup sleep 21600 > /dev/null 2>&1 < /dev/null & echo \$! > /tmp/apollo-busy.inkstrata"
  P=$(rx 'pgrep -x llama-server'); [ -n "$P" ] && rx "kill $P"; log "daily server pids stopped: ${P:-none}"
  for i in $(seq 60); do u=$(rx "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1"); [ "${u:-99999}" -lt 500 ] && break; sleep 5; done
  log "VRAM before (max) ${u} MiB; clocks $(rx "nvidia-smi --query-gpu=clocks.sm,clocks.max.sm,power.limit --format=csv,noheader | tr '\n' ' '")"
}
give_73() { rx "$ST launch --stop > /dev/null 2>&1; kill \$(cat /tmp/apollo-busy.inkstrata) 2>/dev/null; rm -f /tmp/apollo-busy.inkstrata"; systemctl --user start apollo-wake-proxy; log "wake proxy started"; }
serve_pack() {  # serve_pack TAG MODEL|PATH: launch on .73 (a path starting with ~/ or / uses --model-path) and open the tunnel
  case "$2" in "~/"*|/*) SEL="--model-path $2 --custom-label $1" ;; *) SEL="--model $2" ;; esac
  rx "$ST launch $SEL $LAUNCH > ~/strata_launch_$1.log 2>&1"; log "$1 launch ($SEL) rc=$? $(rx "grep -i -E 'serving|address|error|fail' ~/strata_launch_$1.log | tail -2 | tr '\n' ' '")"
  ssh -o BatchMode=yes -N -L $TPORT:127.0.0.1:8085 $HOST & TUN=$!
  for i in $(seq 150); do curl -s -m 3 127.0.0.1:$TPORT/v1/models | grep -q -i inkling && return 0; sleep 2; done; return 1
}
stop_pack() { rx "$ST launch --stop > /dev/null 2>&1"; kill $TUN 2>/dev/null; wait $TUN 2>/dev/null; sleep 5; }
