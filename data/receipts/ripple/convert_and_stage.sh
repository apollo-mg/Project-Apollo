#!/usr/bin/env bash
# After download_ripple.sh, on the desktop: convert the official BF16 weights to a BF16 GGUF (on the NAS: the desktop
# cannot hold the safetensors, a BF16 GGUF and a quant at once), quantize it to Q6_K with llama-quantize built from the
# same llama.cpp commit (67107ac34f), hash it, wait for the DeepSeek move to free .194, copy it there, check the hash.
# Q6_K, not Q8_0: Ripple always reasons, and Q8_0 (~69 GB) does not fit the four P100s (64 GB); its CPU layers would cut
# a dense 65B to ~2 t/s (~1.5 days for M1). Q6_K (~53 GB) is GPU-resident.
# Log: /mnt/TG_2TB/AI/Models/ripple-65b-gguf/stage.log (last line STAGED <sha256> or FAILED ...).
echo $$ > /tmp/ripple_stage.pid
set -u
ROOT=/mnt/TG_2TB/Projects/Apollo; LC=$ROOT/engines/llama_cpp_67107ac
SRC=/mnt/TG_2TB/AI/Models/ripple-65b; BF=/mnt/HDD/Models/ripple-65b/Ripple-65B-Preview-BF16.gguf
OUTD=/mnt/TG_2TB/AI/Models/ripple-65b-gguf; OUT=$OUTD/Ripple-65B-Preview-Q6_K.gguf
mkdir -p "$OUTD" "$(dirname "$BF")"; LOG=$OUTD/stage.log
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
if [ ! -x "$LC/build_cpu/bin/llama-quantize" ]; then
  log "building llama-quantize (CPU)"
  cmake -S "$LC" -B "$LC/build_cpu" -DGGML_HIP=OFF -DGGML_VULKAN=OFF -DGGML_CUDA=OFF -DLLAMA_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release > "$OUTD/build_cpu.log" 2>&1 \
    && cmake --build "$LC/build_cpu" -j 12 --target llama-quantize >> "$OUTD/build_cpu.log" 2>&1 || { log "FAILED: quantize build"; exit 1; }
fi
while [ "$(systemctl --user show ripple-dl -p ActiveState --value 2>/dev/null)" = active ]; do sleep 60; done
tail -1 "$SRC/download.log" | grep -q "ALL OK$" || { log "FAILED: download did not end ALL OK: $(tail -1 "$SRC/download.log")"; exit 1; }
cd /tmp   # never run from the download directory
if [ ! -s "$BF" ]; then
  log "converting to BF16 GGUF"
  "$ROOT/venv_cachyos/bin/python3" "$LC/convert_hf_to_gguf.py" "$SRC" --outtype bf16 --outfile "$BF" > "$OUTD/convert.log" 2>&1 \
    || { log "FAILED: convert exit $? ($(tail -2 "$OUTD/convert.log" | tr '\n' ' '))"; exit 1; }
fi
log "BF16 GGUF $(stat -c %s "$BF") bytes; quantizing to Q6_K"
"$LC/build_cpu/bin/llama-quantize" "$BF" "$OUT" Q6_K 12 > "$OUTD/quantize.log" 2>&1 || { log "FAILED: quantize ($(tail -2 "$OUTD/quantize.log" | tr '\n' ' '))"; exit 1; }
h=$(sha256sum "$OUT" | cut -d' ' -f1); log "quantized: $(stat -c %s "$OUT") bytes sha256 $h"
while [ "$(systemctl --user show ds41-move -p ActiveState --value 2>/dev/null)" = active ]; do sleep 60; done
tail -1 /mnt/HDD/Models/ds41/move.log | grep -q "ALL VERIFIED" || log "note: DeepSeek move did not end ALL VERIFIED ($(tail -1 /mnt/HDD/Models/ds41/move.log))"
free=$(ssh 10.0.0.194 'df --output=avail -B1 ~ | tail -1')
[ "$free" -gt $(( $(stat -c %s "$OUT") + 20000000000 )) ] || { log "FAILED: .194 has $free bytes free"; exit 1; }
ssh 10.0.0.194 'mkdir -p ~/AI/Models/ripple'
scp -q "$OUT" 10.0.0.194:AI/Models/ripple/ || { log "FAILED: scp"; exit 1; }
r=$(ssh 10.0.0.194 'sha256sum ~/AI/Models/ripple/Ripple-65B-Preview-Q6_K.gguf' | cut -d' ' -f1)
[ "$r" = "$h" ] && log "STAGED $h" || log "FAILED: hash on .194 $r != $h"
