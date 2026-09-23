#!/usr/bin/env bash
# One arm per invocation: ./run_kvdepth.sh <ARM>   (BASE first, then any order)
# Resumable: an arm whose dump already exists is skipped. PREREG_KV_DEPTH_MATCHED_ALLOCATION.md.
set -u
ARM=${1:?arm}
R=/mnt/TG_2TB/Projects/Apollo
P=$R/engines/buun-llama-cpp/build_rocm/bin/llama-perplexity   # buun 38ada0e1b
D=/mnt/TG_2TB/AI/kld/kvdepth                                   # base file + logs (not committed)
M=$D/model.gguf                                                 # symlink; sha256 in the prereg
W=/mnt/TG_2TB/AI/kld/wikitext-2-raw/wiki.test.raw
OUT=$R/data/receipts/kv-depth/raw
BASE=$D/base_f16_u16.kld
mkdir -p "$D/logs" "$OUT"
LOCK=$R/run/benchmark.lock

case $ARM in
  BASE) KV=(-ctk f16 -ctv f16) ;;
  C0)   KV=(-ctk f16 -ctv f16) ;;
  C1)   KV=(-ctk vbr -ctv vbr --vbr-vram 2048M) ;;
  Q8)   KV=(-ctk q8_0 -ctv q8_0) ;;
  Q4)   KV=(-ctk q4_0 -ctv q4_0) ;;
  T4)   KV=(-ctk turbo4 -ctv turbo4) ;;
  T3)   KV=(-ctk turbo3_tcq -ctv turbo3_tcq) ;;
  KR)   KV=(-ctk q8_0 -ctv q4_0) ;;
  VR)   KV=(-ctk q4_0 -ctv q8_0) ;;
  T8)   KV=(-ctk turbo8 -ctv turbo8) ;;
  VK)   KV=(-ctk vbr -ctv vbr --vbr-vram 768M) ;;
  V8)   KV=(-ctk vbr -ctv vbr --vbr-vram 544M) ;;
  V4)   KV=(-ctk vbr -ctv vbr --vbr-vram 288M) ;;
  # Amendment 2: frozen VBR (no live free-VRAM clamp); budget via flag AND VBR_BUDGET_MIB
  C1F)  KV=(-ctk vbr -ctv vbr --vbr-vram 2048M); FZ=2048 ;;
  VKF)  KV=(-ctk vbr -ctv vbr --vbr-vram 768M);  FZ=768 ;;
  V8F)  KV=(-ctk vbr -ctv vbr --vbr-vram 544M);  FZ=544 ;;
  V4F)  KV=(-ctk vbr -ctv vbr --vbr-vram 288M);  FZ=288 ;;
  # Amendment 3: budgets trimmed by the observed overshoot so mapped <= static allocation
  V8C)  KV=(-ctk vbr -ctv vbr --vbr-vram 530M);  FZ=530 ;;
  V4C)  KV=(-ctk vbr -ctv vbr --vbr-vram 277M);  FZ=277 ;;
  *) echo "unknown arm $ARM" >&2; exit 2 ;;
esac

if [ "$ARM" = BASE ]; then
  [ -s "$BASE" ] && { echo "skip BASE (exists)"; exit 0; }
  EXTRA=(--kl-divergence-base "$BASE")
else
  [ -s "$BASE" ] || { echo "no base yet" >&2; exit 3; }
  [ -s "$OUT/$ARM.kld.bin" ] && { echo "skip $ARM (dump exists)"; exit 0; }
  EXTRA=(--kl-divergence --kl-divergence-base "$BASE")
  export TURBO_KLD_DUMP="$OUT/$ARM.kld.bin.part"
fi

"$R/tools/benchmark_lock.sh" check >/dev/null 2>&1 && { echo "benchmark lock held; refusing" >&2; exit 4; }
"$R/tools/benchmark_lock.sh" acquire "kv-depth $ARM" $$ >/dev/null
release() { [ "$(cut -f1 "$LOCK" 2>/dev/null)" = "$$" ] && rm -f "$LOCK"; }
trap release EXIT

LOGF=$D/logs/$ARM.log
if [ -n "${FZ:-}" ]; then export VBR_FREEZE=1 VBR_BUDGET_MIB=$FZ VBR_TRACE=$OUT/$ARM.vbrtrace.tsv; fi
t0=$(date +%s)
HIP_VISIBLE_DEVICES=0 "$P" -m "$M" -f "$W" -ngl 99 -fa on -c 32768 -b 512 -ub 512 -v \
  "${KV[@]}" "${EXTRA[@]}" > "$LOGF" 2>&1
rc=$?
wall=$(( $(date +%s) - t0 ))
# PPL mode prints 'Final estimate'; KLD mode prints 'Mean    KLD:' instead (fixed after C0, 2026-09-23)
if [ "$ARM" = BASE ]; then fin=$(grep -c 'Final estimate' "$LOGF"); else fin=$(grep -c 'Mean    KLD:' "$LOGF"); fi
if [ "$ARM" = BASE ]; then
  echo "BASE rc=$rc wall=${wall}s final=$fin size=$(stat -c %s "$BASE" 2>/dev/null)"
  [ "$fin" -ge 1 ] || { echo "BASE FAILED; removing partial base" >&2; rm -f "$BASE"; exit 5; }
else
  if [ "$fin" -ge 1 ] && [ -s "$TURBO_KLD_DUMP" ]; then mv "$TURBO_KLD_DUMP" "$OUT/$ARM.kld.bin"; ok=1; else ok=0; fi
  echo "$ARM rc=$rc wall=${wall}s final=$fin dump_ok=$ok"
  [ $ok = 1 ] || exit 5
fi
