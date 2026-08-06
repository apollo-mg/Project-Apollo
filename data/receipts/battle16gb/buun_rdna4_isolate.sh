#!/usr/bin/env bash
# Localise buun's RDNA4 slowdown to a switch, so the report to him is an isolation result
# rather than a hypothesis.
#
# THE OBSERVATION (FORK_CODEC_SHOOTOUT.md): on RX 9070 XT / gfx1201, buun's fork runs the
# *f16* perplexity base at 28.70 s/pass vs TheTom's 3.56 s/pass -- 237 s vs 32 s over 8
# chunks, ~7.4x. The f16 PPLs agree to 0.012% (5.8993 vs 5.8986), so both forks compute the
# same thing; only the speed differs. The slowdown is present with NO turbo codec requested,
# which rules out turbo kernel cost and points at machinery that arms unconditionally.
#
# Every run of buun's fork prints, even on plain f16:
#     VMEAN tap: graph add armed, 16 live layers (pdim 6144)
#     TCQ1 decode: K/V codebooks (K=baked-in V=baked-in) hotswap=0
#     TCQ decode: context-adaptive V alpha enabled
#
# CANDIDATE SWITCHES found by reading his source (all his own, no patching required):
#   TURBO_MEANSUB_OFF=1   src/llama-graph.cpp:47, commented "explicit disable (A/B + opt-out)".
#                         Disables the V-mean tap -> one broadcast add per layer per graph.
#   TURBO_FUSED_PREFILL=1 ggml/src/ggml-cuda/fattn.cu:2200. The fused turbo MMA path is gated
#                         on (Q->ne[1] <= 4 || turbo_fused_prefill). Perplexity is ~entirely
#                         PREFILL (Q->ne[1] = batch), so with the default 0 the fused path is
#                         SKIPPED for every prefill chunk and it falls back to the slower
#                         route. This should not affect the f16 arm (turbo_kv false), which is
#                         exactly why testing it on BOTH f16 and turbo4 is informative.
#   TURBO_PREFILL_VEC=1   fattn.cu, forces vec prefill for turbo types (his debug override).
#
# DESIGN. Short runs (2 chunks) because we are measuring WALL TIME, not fidelity; the ratio is
# ~8x so 2 chunks is plenty to see it. Tom's fork is the reference ceiling in the same shape.
# Each cell repeated twice: the first touch of a model file pays page-cache cost, and this
# campaign has already been burned once by a cold-cache first load (MTP_DETERMINISM.md).
set -u
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/27B/Qwopus3.5-27B-v3-Q2_K.gguf"
DATASET=/home/mark/wikitext-2-raw/wiki.test.raw
CTX=2048
CHUNKS=${CHUNKS:-2}
NGL=99
OUT=/home/mark/projects/HermesAgent-20/buun_isolate
BUUN=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build/bin
TOM=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin
mkdir -p "$OUT/logs"
LOG=$OUT/isolate.log
TSV=$OUT/results.tsv
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
[ -s "$TSV" ] || printf 'fork\tkv\tswitches\trep\tsecs\tppl\n' > "$TSV"

[ -s "$MODEL" ] || { say "FATAL: model missing"; exit 1; }
[ -s "$DATASET" ] || { say "FATAL: dataset missing"; exit 1; }
busy=$(pgrep -c -f "bin/llama-(perplexity|server)" 2>/dev/null || true)
[ "${busy:-0}" -gt 0 ] && { say "ABORT: a llama process is running"; exit 1; }

cell() {
	local fork=$1 bin=$2 kv=$3 label=$4 rep=$5; shift 5
	local tag; tag=$(echo "${fork}_${kv}_${label}_r${rep}" | tr -c 'A-Za-z0-9_\n' '_')
	local lg=$OUT/logs/${tag}.log
	local t0 t1
	t0=$(date +%s)
	# switches arrive as KEY=VAL words; env applies them only to this process
	env "$@" LD_LIBRARY_PATH="$bin" "$bin/llama-perplexity" \
		-m "$MODEL" -f "$DATASET" -ctk "$kv" -ctv "$kv" \
		-fa on -c "$CTX" --chunks "$CHUNKS" -ngl "$NGL" \
		> "$lg" 2>&1
	local rc=$?; t1=$(date +%s)
	local secs=$((t1-t0))
	local ppl; ppl=$(grep -m1 "Final estimate: PPL" "$lg" | sed 's/.*= *//' | awk '{print $1}')
	if [ $rc -ne 0 ] || [ -z "$ppl" ]; then
		printf '%s\t%s\t%s\t%s\tFAIL\t-\n' "$fork" "$kv" "$label" "$rep" >> "$TSV"
		say "  $fork/$kv/$label r$rep  FAILED rc=$rc"
		grep -iE "error|unsupported|abort" "$lg" | tail -2 | sed 's/^/      /' | tee -a "$LOG"
	else
		printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$fork" "$kv" "$label" "$rep" "$secs" "$ppl" >> "$TSV"
		say "  $fork/$kv/$label r$rep  ${secs}s  PPL=$ppl"
	fi
}

say "=== RDNA4 isolation: buun switches vs Tom reference (${CHUNKS} chunks, ctx $CTX) ==="

for rep in 1 2; do
	say "--- rep $rep ---"
	# reference ceiling
	cell tom  "$TOM"  f16    stock "$rep"
	cell tom  "$TOM"  turbo4 stock "$rep"
	# buun stock
	cell buun "$BUUN" f16    stock "$rep"
	cell buun "$BUUN" turbo4 stock "$rep"
	# buun with the V-mean tap disabled -- the only switch that can plausibly touch the f16 path
	cell buun "$BUUN" f16    meansub_off "$rep" TURBO_MEANSUB_OFF=1
	cell buun "$BUUN" turbo4 meansub_off "$rep" TURBO_MEANSUB_OFF=1
	# buun with the fused MMA prefill path forced on (should matter for turbo4, not f16)
	cell buun "$BUUN" turbo4 fused_prefill "$rep" TURBO_FUSED_PREFILL=1
	cell buun "$BUUN" turbo4 both "$rep" TURBO_MEANSUB_OFF=1 TURBO_FUSED_PREFILL=1
done

say "=== SUMMARY (median of reps) ==="
python3 - "$TSV" <<'PY' | tee -a "$LOG"
import sys,csv,collections
rows=list(csv.DictReader(open(sys.argv[1]),delimiter='\t'))
agg=collections.defaultdict(list)
for r in rows:
    if r["secs"]=="FAIL": continue
    agg[(r["fork"],r["kv"],r["switches"])].append((int(r["secs"]),r["ppl"]))
base={}
print("%-6s %-7s %-15s %8s %10s %s"%("fork","kv","switches","secs","ppl","vs tom"))
for k in sorted(agg):
    v=sorted(x[0] for x in agg[k]); med=v[len(v)//2]; ppl=agg[k][0][1]
    if k[0]=="tom": base[k[1]]=med
    ratio = ("%.2fx"%(med/base[k[1]])) if k[1] in base and base[k[1]] else "-"
    print("%-6s %-7s %-15s %8d %10s %s"%(k[0],k[1],k[2],med,ppl,ratio))
print()
f16_stock=agg.get(("buun","f16","stock")); f16_off=agg.get(("buun","f16","meansub_off"))
if f16_stock and f16_off:
    a=sorted(x[0] for x in f16_stock)[len(f16_stock)//2]
    b=sorted(x[0] for x in f16_off)[len(f16_off)//2]
    print("f16 VMEAN tap A/B: stock %ds -> meansub_off %ds  (%+.1f%%)"%(a,b,100.0*(b-a)/a))
    if b < a*0.7:
        print("  => the V-mean tap accounts for a large share of the f16 slowdown.")
    else:
        print("  => the tap is NOT the main f16 cost; look elsewhere (kernel selection).")
t4_stock=agg.get(("buun","turbo4","stock")); t4_fp=agg.get(("buun","turbo4","fused_prefill"))
if t4_stock and t4_fp:
    a=sorted(x[0] for x in t4_stock)[len(t4_stock)//2]
    b=sorted(x[0] for x in t4_fp)[len(t4_fp)//2]
    print("turbo4 fused-prefill A/B: stock %ds -> TURBO_FUSED_PREFILL=1 %ds  (%+.1f%%)"%(a,b,100.0*(b-a)/a))
PY
say "=== DONE ==="
