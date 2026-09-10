#!/usr/bin/env bash
# What does MTP actually cost in VRAM? Same GGUF, same context, only --spec-type varies.
# Reports total VRAM resident AND the VBR fitter's KV budget, since the operator's article
# claims this model runs on 16 GB at full context -- and the 262k deploy run thrashed.
set -u
B=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin/llama-server
M=/mnt/TG_2TB/AI/Models/gsq-rco/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf
OUT=$HOME/mtp_vram.log; : > $OUT; exec 3>>$OUT
say(){ echo "$*" >&3; }
say "### MTP VRAM cost  $(date -Iseconds)"
say "model=$(basename $M)  $(du -h $M | cut -f1)"
say ""
printf "%-10s %-6s %14s %14s %s\n" "ctx" "mtp" "VRAM_MiB" "KV_budget_MiB" "tier" >&3
for C in 32768 65536 131072 262144; do
  for MTP in off on; do
    EXTRA=""; [ "$MTP" = "on" ] && EXTRA="--spec-type draft-mtp"
    L=/tmp/mv_${C}_${MTP}.log
    setsid nohup $B -m $M -ngl 99 -c $C -np 1 -fa on --kv-unified -ctk vbr -ctv vbr \
      --vbr-floor t2 --vbr-vram auto $EXTRA --reasoning-effort medium --min-p 0 \
      --host 127.0.0.1 --port 8092 > $L 2>&1 & disown
    i=0; while [ $i -lt 40 ]; do grep -qa "listening on\|failed to load\|error while" $L && break; i=$((i+1)); sleep 3; done
    if grep -qa "listening on" $L; then
      sleep 2
      V=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -i "used" | head -1 | grep -oE "[0-9]+" | tail -1)
      VM=$(( V / 1048576 ))
      KB=$(grep -aoE "KV VRAM budget [0-9]+ MiB" $L | grep -oE "[0-9]+" | head -1)
      TIER=$(grep -aoE "priced at the [a-z0-9_]+ floor tier" $L | grep -oE "the [a-z0-9_]+ floor" | awk '{print $2}' | head -1)
      printf "%-10s %-6s %14s %14s %s\n" "$C" "$MTP" "$VM" "${KB:-?}" "${TIER:-?}" >&3
    else
      printf "%-10s %-6s %14s %14s %s\n" "$C" "$MTP" "FAILED" "-" "$(grep -aoiE 'failed to load|not enough|error while' $L | head -1)" >&3
    fi
    pkill -x llama-server; sleep 4
    while ss -ltn 2>/dev/null | grep -q ":8092 "; do sleep 1; done
    sync
  done
done
say ""; say "######## MTP VRAM DONE $(date -Iseconds)"
