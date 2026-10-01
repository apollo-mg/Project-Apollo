#!/usr/bin/env bash
# PREREG_MMVF_SHORTROW.md runner, ON .73. Usage: mmvf_run.sh A|B
# Launch: setsid nohup bash ~/mmvf/mmvf_run.sh A > ~/mmvf/run_A.log 2>&1 < /dev/null & echo $! > ~/mmvf/run_A.pid
# Per leg: gate (no llama-server, no compute apps) before and after; a contaminated leg is rerun (max 3 tries).
set -uo pipefail
W=~/mmvf; PH=$1; OUT=$W/raw_$PH; mkdir -p $OUT
# our perf cases only (mmvf_perf_cases.inc); stock cases that happen to match are harmless (analysis keys on shape)
PERF_RE='m=(10240|32000|16384|4096|8192|2048|320),n=[0-9]+,k=(64|128|256|320|384|512|768|1024|1536|2048|192|96|448|640|4096|10240),bs=\[1,1\],nr=\[1,1\]'
TEST_RE='type(_a)?=(f16|bf16|f32),'
TEST_OPS='MUL_MAT,MUL_MAT_ID,MUL_MAT_VEC_FUSION'

gate() {
  local s a c ac
  s=$(pgrep -x llama-server | wc -l)
  a=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l)
  c=$(nvidia-smi -i 0 --query-gpu=clocks.applications.graphics,clocks.max.sm,temperature.gpu --format=csv,noheader,nounits | tr -d ' ')
  echo "$(date +%T) gate $1 servers=$s apps=$a app_clk,max_clk,temp=$c" >> $OUT/gates.log
  [ "$s" = 0 ] && [ "$a" = 0 ]
}

leg() {  # leg NAME ENV BIN MODE...
  local name=$1 env=$2 bin=$3; shift 3
  for try in 1 2 3; do
    gate "pre $name try$try" || { sleep 60; continue; }
    if [ -n "$env" ]; then
      env GGML_MMVF_TUNE=$env $bin "$@" > $OUT/$name.txt 2> $OUT/$name.err
    else
      $bin "$@" > $OUT/$name.txt 2> $OUT/$name.err
    fi
    echo "$(date +%T) leg $name rc=$? env=${env:-unset}" >> $OUT/gates.log
    # rc=0 is not proof (usage text exits 0): require the mode's own result marker
    if ! grep -qE 'us/run|tests passed' $OUT/$name.txt; then
      echo "$(date +%T) leg $name NO RESULT MARKER -- aborting run" >> $OUT/gates.log; exit 1
    fi
    gate "post $name try$try" && return 0
    mv $OUT/$name.txt $OUT/$name.contaminated$try.txt
  done
  echo "$(date +%T) leg $name FAILED GATE 3x" >> $OUT/gates.log
}

if [ "$PH" = A ]; then
  sha256sum $W/tbo-base $W/tbo-tune > $OUT/binaries.sha256
  leg test_base "" $W/tbo-base test -b CUDA0 -o $TEST_OPS -p "$TEST_RE" -j 4
  leg test_tune_R4 "4,4096" $W/tbo-tune test -b CUDA0 -o $TEST_OPS -p "$TEST_RE" -j 4
  for rep in 1 2 3; do
    for arm in base unset R1 R2 R4 R8; do
      case $arm in
        base)  leg perf_${arm}_r$rep "" $W/tbo-base perf -b CUDA0 -o MUL_MAT -p "$PERF_RE" ;;
        unset) leg perf_${arm}_r$rep "" $W/tbo-tune perf -b CUDA0 -o MUL_MAT -p "$PERF_RE" ;;
        R*)    leg perf_${arm}_r$rep "${arm#R},4096" $W/tbo-tune perf -b CUDA0 -o MUL_MAT -p "$PERF_RE" ;;
      esac
    done
  done
elif [ "$PH" = B ]; then
  sha256sum $W/tbo-base $W/tbo-final > $OUT/binaries.sha256
  leg test_final "" $W/tbo-final test -b CUDA0 -o $TEST_OPS -p "$TEST_RE" -j 4
  for rep in 1 2 3; do
    for arm in base final; do
      leg perf_${arm}_r$rep "" $W/tbo-$arm perf -b CUDA0 -o MUL_MAT -p "$PERF_RE"
    done
  done
fi
echo RUN_${PH}_DONE
