#!/usr/bin/env bash
# RDNA4 (gfx1201) column for jasstrong's narrow-matmul table -- TheTom/llama-cpp-turboquant #362/#363.
# Waits for the GPU to free first: the reported gfx1030 result is a SEGFAULT, and a GPU-side
# fault can reset the device, which would take a live benchmark with it.
set -u
B=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin/test-backend-ops
OUT=/mnt/TG_2TB/Projects/Apollo/data/receipts/rdna4-kernel-census
mkdir -p "$OUT"
LOG=$OUT/raw_rdna4_narrow_matmul.log
: > "$LOG"
log(){ echo "$@" >> "$LOG"; }

F_CRASH='type_a=q8_0,type_b=f32,m=10240,n=4,k=320,'
F_TRIO='type_a=(q8_0|f16),type_b=f32,m=(4|320|10240),n=[14],k=(320|10240),'
F_SWEEP='type_a=(bf16|f16),type_b=f32,m=10240,n=[1-6],k=320,'

# Gate: require the GPU quiet for 3 consecutive checks. A single check can catch a gap
# while the harness restarts llama-server between phases, and AFM-36 says orphaned
# run_agent.py workers outlive the bench that spawned them -- both would contaminate this.
log "waiting for GPU to free ($(date -Iseconds))..."
quiet=0
while [ $quiet -lt 3 ]; do
    busy=""
    pgrep -x llama-server >/dev/null 2>&1 && busy="llama-server"
    for n in run_agent.py run_real.py; do
        pgrep -f "[${n:0:1}]${n:1}" >/dev/null 2>&1 && busy="$busy $n"
    done
    use=$(rocm-smi --showuse 2>/dev/null | grep -oP 'GPU use \(%\): \K[0-9]+' | head -1)
    [ -n "${use:-}" ] && [ "$use" -gt 15 ] && busy="$busy gpu=${use}%"
    if [ -n "$busy" ]; then quiet=0; sleep 30; else quiet=$((quiet+1)); sleep 30; fi
done
log "  GPU quiet for 90s straight; starting $(date -Iseconds)"

{
  echo "=== ENVIRONMENT $(date -Iseconds) ==="
  echo "commit: $(git -C /mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp rev-parse --short HEAD)"
  rocm-smi --showproductname 2>/dev/null | grep -iE 'Card (Series|Model|SKU)' | head -3
  echo "--- clock state at start (receipts must record this) ---"
  rocm-smi --showclocks --showpower 2>/dev/null | grep -iE 'sclk|mclk|Average Graphics Package' | head -6
} >> "$LOG"

# ---- 1. correctness: does jasstrong's shape fault on gfx1201? ----
log ""; log "=== CORRECTNESS: q8_0 m=10240 n=4 k=320 ==="
log "  (reported: segfault on gfx1030; clean on gfx1100 and gfx90a; gfx1201 untried)"
timeout 900 "$B" test -o MUL_MAT -p "$F_CRASH" >> "$LOG" 2>&1
rc=$?
case $rc in
  0)   verdict="PASS - no fault, correctness OK" ;;
  139) verdict="SEGFAULT - reproduces gfx1030 behaviour on RDNA4" ;;
  124) verdict="TIMEOUT/HANG" ;;
  *)   verdict="exit $rc - see output above" ;;
esac
log "  VERDICT: $verdict"

log ""; log "=== CORRECTNESS: full narrow trio + bf16/f16 sweep ==="
timeout 900 "$B" test -o MUL_MAT -p "$F_TRIO" >> "$LOG" 2>&1; log "  trio exit: $?"
timeout 900 "$B" test -o MUL_MAT -p "$F_SWEEP" >> "$LOG" 2>&1; log "  sweep exit: $?"

# ---- 2. perf: the RDNA4 column ----
log ""; log "=== PERF: narrow trio, q8_0 vs f16, n=1 and n=4 ==="
timeout 900 "$B" perf -o MUL_MAT -p "$F_TRIO" >> "$LOG" 2>&1
log ""; log "=== PERF: bf16 vs f16 sweep n=1..6 on m=10240,k=320 ==="
log "  (mmvf thresholds on RDNA4: f16 <= 5 tuned, bf16 <= 3 flat/untuned)"
timeout 900 "$B" perf -o MUL_MAT -p "$F_SWEEP" >> "$LOG" 2>&1

# ---- 3. guards ----
log ""; log "=== GUARDS ==="
# NB: test-backend-ops prints "N runs - X us/run - ... GFLOPS" on a SEPARATE line from the
# MUL_MAT(...) header whenever the CUDA-graph warmup message interleaves. Counting lines that
# match both produces a false alarm -- count the timing lines alone.
n_perf=$(grep -c 'us/run' "$LOG")
log "  perf result lines: $n_perf"
[ "$n_perf" -lt 20 ] && log "  *** WARNING: fewer perf lines than the 26 cases the filters select -- filter may have missed. DO NOT report these numbers without checking. ***"
log "  GPU faults in dmesg since start:"
dmesg 2>/dev/null | grep -iE 'amdgpu.*(ring|reset|fault|timeout)' | tail -5 >> "$LOG" || log "    (dmesg unreadable without privileges)"
log ""; log "=== DONE $(date -Iseconds) ==="
