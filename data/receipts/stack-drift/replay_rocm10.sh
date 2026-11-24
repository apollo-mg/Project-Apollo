#!/bin/bash
# Pre-check for the three-stack drift test (2026-11-24): the desktop's CachyOS update took ROCm 7.2.4 -> 10.1
# (hip-runtime-amd, rocblas, hipblas, comgr, hsa-rocr; kernel 7.3.3 -> 7.3.5) with the llama.cpp binaries unchanged.
# Replay two stored desktop arms on their own binaries, cards and flags; compare answers byte for byte afterwards.
#   FZ_BASE_R10: buun 38ada0e1b build_rocm, Granite 4.1 3B Q8_0 (stored FZ_BASE, 11-23 under ROCm 7.2.4)
#   Q35R_R10:    llama.cpp PR 32588 4bc61eed7 build_rocm, Qwen3.5-9B Q8_0 (stored Q35R, 11-23 under ROCm 7.2.4)
set -u
# ROCM_PREFIX (optional): a private ROCm tree (here 7.2.4 unpacked from the pacman cache) used instead of the system's;
# SUF: arm-name suffix (default _R10, the system ROCm 10.1)
SUF=${SUF:-_R10}
if [ -n "${ROCM_PREFIX:-}" ]; then
  export LD_LIBRARY_PATH=$ROCM_PREFIX/lib:$ROCM_PREFIX/lib/llvm/lib ROCBLAS_TENSILE_LIBPATH=$ROCM_PREFIX/lib/rocblas/library
fi
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/stack-drift; QA=$R/data/receipts/quant-abstention
PY=$R/venv_cachyos/bin/python3; PORT=8095; S=$H/raw/state_replay$SUF.log; log() { echo "$* $(date '+%F %T')" >> $S; }
log "start; arms *$SUF; ROCM_PREFIX=${ROCM_PREFIX:-system} (system: $(pacman -Q hip-runtime-amd rocblas | tr '\n' ' ')); kernel $(uname -r)"
run() {  # run ARM BIN MODEL "FLAGS" META
  $2/llama-server -m $3 $4 --host 127.0.0.1 --port $PORT > $H/raw/server_$1.log 2>&1 &
  SP=$!; ok=0; for i in $(seq 180); do curl -s 127.0.0.1:$PORT/health 2>/dev/null | grep -q ok && { ok=1; break; }; kill -0 $SP 2>/dev/null || break; sleep 2; done
  if [ $ok = 1 ]; then
    ( cd $QA && $PY run_main.py --url http://127.0.0.1:$PORT --arm $1 --max-tokens 1024 --usage $6 --meta "$5" > $H/raw/run_$1.log 2>&1 )
    log "$1 rc=$? rows=$(( $(wc -l < $QA/raw/main_$1.jsonl) - 1 ))"
  else log "$1 server failed"; fi
  kill $SP 2>/dev/null; wait $SP 2>/dev/null
}
run FZ_BASE$SUF $R/engines/buun-llama-cpp/build_rocm/bin /mnt/TG_2TB/models_small/gguf/granite-4.1-3b-Q8_0.gguf \
  "-ngl 99 -c 4096 -np 1 -ctk f16 -ctv f16 --cache-ram 0" \
  '{"model": "granite-4.1-3b-Q8_0.gguf (no adapter)", "build": "buun 38ada0e1b build_rocm", "host": "RX 9070 XT", "rocm": "'"${ROCM_PREFIX:-system 10.1}"'", "note": "replay of FZ_BASE after the ROCm 7.2.4 -> 10.1 update"}' "--no-think-check"
run Q35R$SUF $R/engines/llama_cpp_4bc61eed/build_rocm/bin /mnt/TG_2TB/AI/Models/sci-distill-gguf/Qwen3.5-9B-Q8_0.gguf \
  "-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0" \
  '{"model": "Qwen3.5-9B-Q8_0.gguf", "sha256": "f904644b...", "commit": "4bc61eed7 (llama.cpp PR 32588)", "host": "RX 9070 XT", "rocm": "'"${ROCM_PREFIX:-system 10.1}"'", "note": "replay of Q35R after the ROCm 7.2.4 -> 10.1 update"}' ""
log REPLAY_DONE
