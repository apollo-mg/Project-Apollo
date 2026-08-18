#!/usr/bin/env bash
# S2 - DFlash vs MTP on Tesla P100 (sm_60). Port of the RX 9070 XT drafter showdown,
# same target file, same prompt set, same n_max sweep, so the two are comparable.
#
# THE QUESTION: on the 9070XT DFlash climbed MONOTONICALLY with depth
# (116.68 -> 140.03 -> 150.66 t/s at n=3/7/15) while MTP peaked at n=3 and lost 29% by
# n=15. DFlash denoises up to 16 positions in ONE drafter pass, so depth is nearly free
# there; MTP pays n sequential head passes. Does that invert on compute-bound hardware?
#
# WHY P100 MIGHT INVERT IT: spec decode converts N sequential memory-bound target passes
# into one pass with an N-token batch - trading bandwidth for compute. P100 is
# bandwidth-rich / compute-poor relative to RDNA4 (732 GB/s HBM2 against ~9.3 TF fp32;
# the 9070XT is ~640 GB/s against far more compute), and these cards are capped at 150 W,
# NOT the 300 W the S2 backlog entry assumed. So the wide verification batch should
# saturate compute sooner here.
#
# PRE-REGISTERED, before any arm runs:
#   P1 DFlash still beats MTP at every depth            conf 0.75
#   P2 DFlash's n=3 -> n=15 gain is SMALLER than the 9070XT's +29%   conf 0.80
#   P3 DFlash's curve is non-monotonic (peaks before n=15)           conf 0.55
#   P4 MTP still peaks at or below n=3                               conf 0.70
#   P5 acceptance rates track the 9070XT within a few points (same model,
#      same prompts, drafter quality is hardware-independent)        conf 0.85
#      -> P5 is the CONTROL: if acceptance diverges materially, the port is
#         suspect and the throughput numbers should not be read.
set -u
B=~/moe-cache-test-src/build-cuda/bin
TGT=~/dflash_models/Qwen3.5-9B-Q8_0.gguf
DFT=~/dflash_models/Qwen3.5-9B-DFlash.Q8_0.gguf
S=~/dflash_s2
PORT=8082
mkdir -p "$S"
export HOST="http://127.0.0.1:$PORT"

# Power/clock sampler. NOTE: an earlier version returned the PID via command
# substitution -- p=$(pw_sample tag) -- which HANGS FOREVER: $() waits for EOF on the
# pipe and the backgrounded infinite loop inherits stdout and never closes it. The
# sampler ran, the benchmark never started. Use a global + redirected stdout instead.
PW_PID=""
pw_start(){
  local tag=$1
  ( while :; do
      nvidia-smi --query-gpu=index,power.draw,clocks.sm,utilization.gpu,temperature.gpu \
                 --format=csv,noheader,nounits >> "$S/pw_${tag}.csv" 2>/dev/null
      sleep 2
    done ) >/dev/null 2>&1 &
  PW_PID=$!
}
pw_stop(){ [ -n "$PW_PID" ] && { kill "$PW_PID" 2>/dev/null; pkill -P "$PW_PID" 2>/dev/null; }; PW_PID=""; }

launch() {
    pkill -x llama-server 2>/dev/null; sleep 3
    LD_LIBRARY_PATH=$B "$B/llama-server" \
        -m "$TGT" -ngl 99 -c 8192 --jinja \
        --host 127.0.0.1 --port $PORT "$@" \
        > "$S/srv.log" 2>&1 &
    for i in $(seq 1 240); do
        curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && return 0
        pgrep -x llama-server >/dev/null || { echo "SERVER DIED"; tail -25 "$S/srv.log"; return 1; }
        sleep 1
    done
    echo "TIMEOUT waiting for server"; return 1
}

run() { tag=$1; shift; echo "### $tag  $(date -Is)"; launch "$@" || return 1
        grep -iE "n_max=|block_size=|adding speculative" "$S/srv.log" | head -3
        pw_start "$tag"
        python3 "$S/dflash_ab.py" "$tag"
        pw_stop
        if [ -s "$S/pw_${tag}.csv" ]; then
          awk -F, '{n++; p+=$2; c+=$3; u+=$4; if($2>pk)pk=$2; if($4>50){bn++; bp+=$2; bc+=$3}} END{
            if(n)printf "    all-samples power %.1f W  sm %.0f MHz  util %.0f%%  peak %.1f W  (n=%d)\n", p/n, c/n, u/n, pk, n;
            if(bn)printf "    BUSY(util>50) power %.1f W  sm %.0f MHz  (n=%d)  headroom vs 150W cap: %.1f W\n", bp/bn, bc/bn, bn, 150-bp/bn}' "$S/pw_${tag}.csv"
        fi
        echo; }

echo "### S2 DFlash vs MTP on P100 (sm_60)  $(date -Is)"
nvidia-smi --query-gpu=index,name,power.limit --format=csv,noheader | sed 's/^/###   /'
echo

run off
for n in 3 7 15; do run "mtp_n$n" --spec-type draft-mtp --spec-draft-n-max $n; done
for n in 3 7 15; do run "dfl_n$n" -md "$DFT" --spec-type draft-dflash -ngld 99 --spec-draft-n-max $n; done

pkill -x llama-server 2>/dev/null
echo "### S2 DONE $(date -Is)"
