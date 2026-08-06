#!/usr/bin/env bash
# turboquant #241 -- verify the wave64 subgroup-ballot fix on RX 580 / Polaris10 (subgroup 64).
#
# Build under test: /mnt/usb/tqbin_w64 = 11a8377bd (one commit on 9d1d46e36).
# Reference: /mnt/usb/mx_fix from 2026-07-31, which was byte-identical to the unpatched
# 9971 build in all 6 shared cells -- so those SHAs ARE the unpatched behaviour.
#
# CELL ORDER IS LOAD-BEARING. TURBO3_241_FIX_VERIFICATION.md established these outputs are
# execution-order dependent, not time dependent: the f16/f16 control reproduces exactly when
# the preceding cell is the same, and differs when it is not. The order below is copied
# verbatim from turbo3_fix_verify.sh matrix(). Do not reorder to "group" the turbo3 cells.
#
# Predictions logged before this ran: PREDICTIONS_turbo3_wave64.md
#   P-W1 three turbo3-V cells reach gzip >= 0.45
#   P-W2 turbo3 cells NOT byte-identical to reference  <-- the cheap falsifier
#   P-W3 kf16_vf16 IS byte-identical (ad9dd4fa776f)    <-- specificity
#   P-W4 both turbo4-V cells byte-identical            <-- specificity
set -u
BIN=/mnt/usb/tqbin_w64
MODEL=/mnt/usb/crow9b.gguf
CTX=16384
export VK_DRIVER_FILES=/usr/share/vulkan/icd.d/radeon_icd.json
MASTER=/mnt/usb/w64_verify.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$MASTER"; }

cat > /mnt/usb/probe_w64.json <<'EOF'
{"model":"q","temperature":0,"max_tokens":500,"cache_prompt":false,
 "messages":[{"role":"user","content":"Write a 500-word essay about Linux."}]}
EOF

# Reference SHAs + gzip from the unpatched/old-fix run (identical to each other).
ref_sha() { case "$1" in
	kturbo4_vturbo3) echo "173da68272cc 0.2736";;
	kf16_vf16)       echo "ad9dd4fa776f 0.5097";;
	kturbo4_vturbo4) echo "9e33a09474a1 0.5024";;
	kturbo4_vturbo2) echo "0b3b5c4235d5 0.5021";;
	kturbo3_vturbo3) echo "65e01d083c83 0.3474";;
	kf16_vturbo3)    echo "b539962f600d 0.1753";;
	kturbo3_vf16)    echo "4dfeae533123 0.4299";;
	*) echo "unknown -";; esac; }

run_cell() {
	local ctk=$1 ctv=$2 port=$3
	local tag="k${ctk}_v${ctv}"
	local out=/mnt/usb/mx_w64
	local slog=$out/server_${tag}.log
	mkdir -p "$out"
	LD_LIBRARY_PATH="$BIN" setsid "$BIN/llama-server" -m "$MODEL" -c "$CTX" -b 1024 -ub 512 \
		-ctk "$ctk" -ctv "$ctv" -fa on -np 1 -ngl 99 --cache-ram 0 \
		--port "$port" --host 127.0.0.1 --jinja > "$slog" 2>&1 < /dev/null &
	local pid=$! ok=0 i
	for i in $(seq 1 400); do
		curl -s -m 5 "http://127.0.0.1:$port/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
		kill -0 "$pid" 2>/dev/null || break
		sleep 2
	done
	if [ "$ok" != 1 ]; then
		say "    $tag SERVER FAILED"
		grep -iE "error|out of memory|assert" "$slog" | tail -3 | sed 's/^/      /' | tee -a "$MASTER"
		kill -9 "$pid" 2>/dev/null; sleep 8; return
	fi
	curl -s -m 900 "http://127.0.0.1:$port/v1/chat/completions" \
		-H 'Content-Type: application/json' -d @/mnt/usb/probe_w64.json > "$out/resp_${tag}.json"
	python3 - "$out/resp_${tag}.json" "$tag" "$(ref_sha "$tag")" <<'PY' | tee -a "$MASTER"
import json,sys,gzip,re,hashlib
p,tag,ref = sys.argv[1],sys.argv[2],sys.argv[3]
ref_sha,ref_gz = (ref.split()+["-","-"])[:2]
try:
    m=json.load(open(p))["choices"][0]["message"]
    t=(m.get("content") or "")+(m.get("reasoning_content") or "")
except Exception as e:
    print("    %-16s PARSE FAIL %s"%(tag,e)); raise SystemExit
b=t.encode("utf-8","ignore")
ratio=len(gzip.compress(b,6))/max(len(b),1)
sha=hashlib.sha256(t.encode()).hexdigest()[:12]
same="SAME-AS-UNPATCHED" if sha==ref_sha else "CHANGED"
print("    %-16s gzip=%.4f (ref %s) chars=%-5d sha=%s (ref %s) %s"%(
    tag,ratio,ref_gz,len(t),sha,ref_sha,same))
print("    %-16s %r"%("",t[:100]))
PY
	kill "$pid" 2>/dev/null
	local w; for w in $(seq 1 40); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
	kill -9 "$pid" 2>/dev/null; sleep 8
}

say "===== turbo3 #241 WAVE64 BALLOT FIX VERIFICATION ====="
say "build: $(LD_LIBRARY_PATH=$BIN $BIN/llama-server --version 2>&1 | grep -i version | head -1)"
say "gpu:   $(LD_LIBRARY_PATH=$BIN $BIN/llama-server --list-devices 2>/dev/null | grep Vulkan0)"

say "--- test-backend-ops FLASH_ATTN_EXT (expect: still passes; read path was never broken) ---"
LD_LIBRARY_PATH=$BIN timeout 2400 $BIN/test-backend-ops test -o FLASH_ATTN_EXT > /mnt/usb/tbo_w64_fa.log 2>&1
say "    rc=$?"
grep -iE "turbo3" /mnt/usb/tbo_w64_fa.log | grep -iE "fail|ok" | head -6 | sed 's/^/      /' | tee -a "$MASTER"

say "--- test-backend-ops SET_ROWS (expect: still skipped 0/0, prints OK -- the trap) ---"
LD_LIBRARY_PATH=$BIN timeout 1800 $BIN/test-backend-ops test -o SET_ROWS > /mnt/usb/tbo_w64_sr.log 2>&1
say "    rc=$?"
grep -iE "TURBO3|TURBO4" /mnt/usb/tbo_w64_sr.log | head -6 | sed 's/^/      /' | tee -a "$MASTER"
tail -4 /mnt/usb/tbo_w64_sr.log | sed 's/^/      /' | tee -a "$MASTER"

say "########## MATRIX: 11a8377bd (wave64 ballot fix) ##########"
run_cell turbo4 turbo3 8143
run_cell f16    f16    8143
run_cell turbo4 turbo4 8143
run_cell turbo4 turbo2 8143
run_cell turbo3 turbo3 8143
run_cell f16    turbo3 8143
run_cell turbo3 f16    8143

say "===== ALL DONE ====="
