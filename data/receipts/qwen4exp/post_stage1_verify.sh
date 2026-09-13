#!/usr/bin/env bash
# Post-Stage-1 checks for PREREG_FLASHNEXT_RESIDENCY.md (Amendment 2, item 2) plus the NCCL ctest rerun owed by
# RESULT_O11_CLEAN_BUILD.md. LOAD ONLY -- no requests, no timing. Waits for the Stage 1 driver to finish and
# refuses to run if it aborted. Runs ON .194, launched detached.
set -u
R=~/flashnext_res; V=$R/verify; mkdir -p "$V"
BIN=~/buun-c7f114d34/build_sm60/bin/llama-server
M=~/AI/Models
Q2=$M/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf
IQ4=$M/flashnext/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf
# identical to the driver's COMMON except the port and -lv (the default verbosity prints no loader lines)
COMMON="-c 4096 -np 1 -b 2048 -ub 512 -fa on --jinja -fit off -sm layer -ctk f16 -ctv f16 --host 127.0.0.1 --port 8094 -lv 4"
export GGML_CUDA_ALLREDUCE=internal CUDA_VISIBLE_DEVICES=0,1,2,3
say () { echo "$(date '+%F %T') $*" >> "$V/verify.log"; }

say "verifier up (pid $$), waiting for STAGE 1 COMPLETE"
for i in $(seq 1 120); do
  grep -q "STAGE 1 COMPLETE" "$R/driver.log" 2>/dev/null && break
  grep -q "ABORT" "$R/driver.log" 2>/dev/null && { say "ABORT: the Stage 1 driver aborted -- not verifying"; exit 1; }
  sleep 30
done
grep -q "STAGE 1 COMPLETE" "$R/driver.log" || { say "ABORT: Stage 1 never completed"; exit 1; }
sleep 20
pgrep -x llama-server >/dev/null && { say "ABORT: a llama-server is still running"; exit 1; }

gpus_clear () { for i in $(seq 1 90); do [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 500 ] && return 0; sleep 1; done; return 1; }
check () {   # label model extra-flags...
  local label=$1 model=$2; shift 2
  local log="$V/load_$label.log"
  "$BIN" -m "$model" $COMMON "$@" > "$log" 2>&1 &
  local pid=$!
  for i in $(seq 1 300); do
    curl -sf http://127.0.0.1:8094/health >/dev/null 2>&1 && break
    kill -0 "$pid" 2>/dev/null || break
    sleep 2
  done
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  say "$label: $(grep -c 'model buffer size' "$log") buffer lines | KV: $(grep -oE '\b[KV] \([A-Za-z0-9_]+\)' "$log" | sort -u | tr '\n' ' ')| pipeline: $(grep -ioE 'pipeline parallelism[^|]{0,40}' "$log" | head -1)"
  gpus_clear || say "WARN: GPUs did not clear after $label"
}
check F-Q2  "$Q2"  -ngl 99
check P-Q2  "$Q2"  -ngl 44
check X-Q2  "$Q2"  -ngl 99 -ot 'blk\.(44|45|46|47)\.ffn_(up|down|gate)_exps=CPU'
check P-IQ4 "$IQ4" -ngl 44

say "NCCL ctest rerun, with GGML_CUDA_ALLREDUCE=internal"
cd ~/buun-c7f114d34/build_sm60 && timeout 900 ctest -R "exl3-(shard-matrix|expert)" --output-on-failure > "$R/ctest_exl3_allreduce_internal.txt" 2>&1
say "ctest (allreduce=internal): $(grep -E 'tests passed|tests failed' "$R/ctest_exl3_allreduce_internal.txt" | tail -1)"
say "=== VERIFY COMPLETE ==="
