#!/bin/bash
# Runs ON .194. PREREG_VBR_RATE_DISTORTION.md.   ./run_s4.sh ARM GPU   (REF must finish before any other arm)
# Resumable: an arm whose dump exists is skipped. Completion is judged by the log line, not rc (AFM-47).
set -u
ARM=${1:?arm}; GPU=${2:?gpu}
W=~/s4
P=~/buun-llama-cpp/build_sm60_0920/bin/llama-perplexity   # buun 08826ad6e
M=~/AI/Models/ladder_ud/Qwen3.8-27B-UD-Q2_K_XL.gguf
T=$W/wiki.test.raw
BASE=$W/base_f16_u16.kld
mkdir -p $W/dumps $W/logs $W/traces
export GGML_CUDA_ALLREDUCE=internal CUDA_VISIBLE_DEVICES=$GPU
FLAGS=(-ngl 99 -fa on -c 16384 -b 512 -ub 512 -v)   # -v: the KV buffer size line only prints verbose
f16mib () { grep -o 'KV buffer size = *[0-9.]*' $W/logs/REF.log | grep -o '[0-9.]*$' | sort -n | tail -1; }   # max: the first line can read 0.00
case $ARM in
  REF) KV=(-ctk f16 -ctv f16);;
  C0)  KV=(-ctk f16 -ctv f16);;          # Amendment 2 (post-hoc): is the instrument bit-exact on Pascal?
  Q8)  KV=(-ctk q8_0 -ctv q8_0);;
  Q4)  KV=(-ctk q4_0 -ctv q4_0);;
  T4)  KV=(-ctk turbo4 -ctv turbo4);;
  T3)  KV=(-ctk turbo3_tcq -ctv turbo3_tcq);;
  VF|V75|V55|V40|V29|V22|V16|V40F4|V29F4|V22F4)
    case $ARM in VF) F=2.0;; V75) F=0.75;; V55) F=0.55;; V40*) F=0.40;; V29*) F=0.29;; V22*) F=0.22;; V16) F=0.16;; esac
    FLOOR=t1; case $ARM in *F4) FLOOR=t4;; esac   # Amendment 2 (post-hoc): .73's real floor
    FM=$(f16mib); [ -n "$FM" ] || { echo "ABORT $ARM: no f16 KV size in REF.log"; exit 3; }
    B=$(python3 -c "print(int(round($FM*$F)))")
    KV=(-ctk vbr -ctv vbr --vbr-vram ${B}M --vbr-floor $FLOOR)
    export VBR_FREEZE=1 VBR_BUDGET_MIB=$B VBR_TRACE=$W/traces/$ARM.vbrtrace.tsv;;
  *) echo "unknown arm $ARM"; exit 2;;
esac
L=$W/logs/$ARM.log; t0=$(date +%s)
echo "## $ARM gpu=$GPU $(date -Is) $(nvidia-smi -i $GPU --query-gpu=clocks.sm,power.limit --format=csv,noheader) ${VBR_BUDGET_MIB:+budget=${VBR_BUDGET_MIB}MiB}"
if [ $ARM = REF ]; then
  [ -s $BASE ] && { echo "skip REF"; exit 0; }
  $P -m $M -f $T "${FLAGS[@]}" "${KV[@]}" --kl-divergence-base $BASE > $L 2>&1
  grep -q "Final estimate" $L || { echo "ABORT: REF failed"; rm -f $BASE; tail -5 $L; exit 1; }
else
  D=$W/dumps/$ARM.kld.bin; [ -s $D ] && { echo "skip $ARM"; exit 0; }
  [ -s $BASE ] || { echo "ABORT $ARM: no base"; exit 3; }
  TURBO_KLD_DUMP=$D.part $P -m $M -f $T "${FLAGS[@]}" "${KV[@]}" --kl-divergence --kl-divergence-base $BASE > $L 2>&1
  if grep -q "Mean    KLD:" $L && [ -s $D.part ]; then mv $D.part $D; else echo "ABORT: $ARM failed"; tail -5 $L; exit 1; fi
fi
echo "   $ARM ok $(( $(date +%s)-t0 ))s $(grep -m1 'Mean    KLD:' $L) $(grep -o 'KV buffer size = *[0-9.]* MiB' $L | sort -t= -k2 -n | tail -1)"
