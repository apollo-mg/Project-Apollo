#!/usr/bin/env bash
# MTP head vs DFlash block-diffusion drafter, same target, same harness.
#
# WHY THIS TARGET FILE: unsloth's MTP variant of Qwen3.5-9B carries the MTP head
# inside the file (9.11 GiB vs 8.87 for the plain build -- the delta IS the head).
# That same file also serves as the DFlash target, so every arm below runs against
# a byte-identical target and the drafter is the only variable. Running MTP on one
# file and DFlash on another would confound the comparison with a target change.
#
# WHY SWEEP n_max FOR BOTH: the two drafters pay for depth differently and this is
# the whole architectural point.
#   MTP    proposes one token per head pass, so depth n costs n sequential passes
#          and each token conditions on the last -- quality holds, cost is linear.
#   DFlash denoises a block of up to 16 in ONE drafter pass, so depth is nearly
#          free, but tokens inside a block cannot condition on each other.
# A single depth would flatter whichever architecture it happened to suit.
#
# Stock default for both is n_max=3 (common.h:325), which is the number most
# people will actually run, so it is included as its own arm rather than assumed.
set -u
B=/home/mark/moe-cache-test/src/build-hip/bin
# space-free symlinks: an unquoted path with a space killed the first run
M=/mnt/TG_2TB/AI/Models/qwen35
TGT=$M/mtp-Q8_0.gguf
DFT=$M/dflash-Q8_0.gguf
S=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
PORT=8082

launch() {                       # args passed as an array to survive the space in the path
    pkill -x llama-server 2>/dev/null; sleep 3
    LD_LIBRARY_PATH=$B "$B/llama-server" \
        -m "$TGT" -ngl 99 -c 8192 --jinja \
        --host 127.0.0.1 --port $PORT "$@" \
        > "$S/srv_showdown.log" 2>&1 &
    for i in $(seq 1 180); do
        curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && return 0
        pgrep -x llama-server >/dev/null || { echo "SERVER DIED"; tail -25 "$S/srv_showdown.log"; return 1; }
        sleep 1
    done
    echo "TIMEOUT waiting for server"; return 1
}

run() { tag=$1; shift; echo "### $tag  $(date -Is)"; launch "$@" || return 1
        grep -iE "n_max=|block_size=|adding speculative" "$S/srv_showdown.log" | head -3
        $PY "$S/dflash_ab.py" "$tag"; echo; }

run off

for n in 3 7 15; do
    run "mtp_n$n"    --spec-type draft-mtp    --spec-draft-n-max $n
done

for n in 3 7 15; do
    run "dfl_n$n"    -md "$DFT" --spec-type draft-dflash -ngld 99 --spec-draft-n-max $n
done

pkill -x llama-server 2>/dev/null
echo "### SHOWDOWN DONE $(date -Is)"
