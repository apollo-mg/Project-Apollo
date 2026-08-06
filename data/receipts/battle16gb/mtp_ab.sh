#!/usr/bin/env bash
# MTP A/B on Qwen3.6-35B-A3B: does speculative decoding change WHAT the model says,
# and does it stay deterministic at temperature 0?
#
# THE QUESTION (Mark, 2026-07-29). TheTom's fork keeps the upstream convention
# --spec-type draft-mtp --spec-draft-n-max N. This model ships the MTP head:
# qwen35moe.nextn_predict_layers = 1, tensors blk.40.nextn.{eh_proj,enorm,hnorm,
# shared_head_norm}.weight (41 blocks vs Ornith's 40 -- block 40 IS the head).
#
# WHY DETERMINISM IS THE FIRST MEASUREMENT, NOT THE LAST.
# Greedy speculative decoding is meant to be EXACTLY lossless: a drafted token is kept only
# if it matches the target model's argmax, so the emitted sequence should equal the
# non-speculative one token for token. But Battle16GB already receipted MTP on Gemma as
# "lossless-in-distribution, not bit-identical" -- batched verification changes float
# reduction order, and on a 2-bit MoE the argmax margin between top-1 and top-2 can be
# small enough for that to flip a token.
# This entire campaign's K=1 legitimacy rests on verified determinism. If MTP breaks it,
# the MTP arm needs K=3 and the 15% scenario-flip floor applies (HA20_SAMPLING_ARMS.md).
# So: measure it before spending an hour on scenarios.
#
# NOTE ON SCOPE: Qwen3.6-35B-A3B is the BASE model; Ornith-1.0-35B is deepreinforce-ai's
# fine-tune of it. This is a clean WITHIN-MODEL A/B on Qwen3.6. Comparing either arm's
# HA-20 score to Ornith's 14 would confound fine-tune with MTP.
#
# Arms differ ONLY by the two spec flags. Same model file, ctx, KV, batch, engine.
set -u
BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/35B-A3B/Qwen3.6-35B-A3B-UD-IQ2_M.gguf"
OUT=/home/mark/projects/HermesAgent-20/mtp_ab
PROBE=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/detprobe.json
PORT=${PORT:-8108}
mkdir -p "$OUT"
LOG=$OUT/mtp_ab.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
export LD_LIBRARY_PATH="$BIN:${LD_LIBRARY_PATH:-}"

SRV=""
stop() {
	[ -n "$SRV" ] || return 0
	kill "$SRV" 2>/dev/null
	for i in $(seq 1 30); do kill -0 "$SRV" 2>/dev/null || break; sleep 1; done
	kill -9 "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; SRV=""; sleep 6
}
trap stop EXIT

# Kill by PID captured at launch. NEVER pkill/pgrep -f on a pattern that also matches this
# script's own shell -- that has silently killed three probes this session.
arm() {
	local label=$1; shift
	local slog=$OUT/server_${label}.log
	say "arm=$label  extra flags: $*"
	local idle; idle=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -i Used | grep -oE '[0-9]{6,}' | head -1)
	setsid "$BIN/llama-server" -m "$MODEL" -c 65536 -b 1024 -ub 512 \
		-ctk f16 -ctv f16 -cb -fa on -np 1 -ngl 99 --cache-ram 0 \
		--port "$PORT" --host 127.0.0.1 --jinja "$@" \
		> "$slog" 2>&1 < /dev/null &
	SRV=$!
	local ok=0
	for i in $(seq 1 180); do
		curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
		kill -0 "$SRV" 2>/dev/null || { say "  SERVER DIED"; tail -15 "$slog" | tee -a "$LOG"; return 1; }
		sleep 2
	done
	[ "$ok" = 1 ] || { say "  NEVER HEALTHY"; return 1; }
	local used; used=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -i Used | grep -oE '[0-9]{6,}' | head -1)
	say "  vram: idle=$idle used=$used  server=$(awk -v a="$used" -v b="$idle" 'BEGIN{printf "%.2f",(a-b)/1073741824}') GiB"
	for i in 1 2 3; do
		curl -s -m 400 "http://127.0.0.1:$PORT/v1/chat/completions" \
			-H 'Content-Type: application/json' -d @"$PROBE" > "$OUT/${label}_$i.json"
	done
	# tg lines are the fork's own decode accounting; with MTP on, tokens/s includes accepted
	# draft tokens, which is exactly the number a user feels.
	say "  decode: $(grep -oE 'tg = +[0-9.]+ t/s' "$slog" | tail -3 | tr '\n' ' ')"
	grep -iE "n_drafted|n_accept|acceptance|speculative" "$slog" | tail -3 | sed 's/^/      /' | tee -a "$LOG"
	stop
}

arm base
arm mtp --spec-type draft-mtp --spec-draft-n-max 2

say "=== COMPARISON ==="
python3 - "$OUT" <<'PY' | tee -a "$LOG"
import json,hashlib,sys,os
d=sys.argv[1]
def body(p):
    m=json.load(open(p))["choices"][0]["message"]
    return (m.get("reasoning_content") or "")+"|"+(m.get("content") or "")
res={}
for label in ("base","mtp"):
    hs=[]
    for i in (1,2,3):
        p=os.path.join(d,"%s_%d.json"%(label,i))
        if os.path.exists(p):
            b=body(p); hs.append((hashlib.sha256(b.encode()).hexdigest()[:16], len(b), b))
    res[label]=hs
    if hs:
        stable = len(set(h for h,_,_ in hs))==1
        print("%-5s %d draws  sha=%s  chars=%d  self-consistent=%s"%(
            label,len(hs),hs[0][0],hs[0][1],"YES" if stable else "*** NO ***"))
if res.get("base") and res.get("mtp"):
    b0,m0=res["base"][0][2],res["mtp"][0][2]
    if b0==m0:
        print("\nMTP vs base: BYTE-IDENTICAL -> speculative decoding is exactly lossless here.")
    else:
        i=next((k for k in range(min(len(b0),len(m0))) if b0[k]!=m0[k]), min(len(b0),len(m0)))
        print("\nMTP vs base: DIVERGES at char %d of %d"%(i,min(len(b0),len(m0))))
        print("  base: ...%s"%b0[max(0,i-60):i+60].replace("\n","\\n"))
        print("  mtp : ...%s"%m0[max(0,i-60):i+60].replace("\n","\\n"))
PY
say "=== DONE ==="
