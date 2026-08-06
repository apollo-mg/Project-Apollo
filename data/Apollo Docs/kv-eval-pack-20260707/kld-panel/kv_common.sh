# kv_common.sh — shared library for the KV-cache regression harness.
# Sourced by kv_kld_sweep.sh, kv_bench.sh, kv_status.sh. Not executable on its own.
#
# Goal: dependable, fork-agnostic regression of the *custom* KV-cache types a given
# llama.cpp build supports (turbo*, tcq*, or whatever a fork adds) — against logit
# bases (KLD/PPL) and against throughput (llama-bench). KV types are auto-detected
# from the binary's own --help, never hardcoded, so a new fork needs zero edits.
#
# Override any default via environment, e.g.:
#   BIN_DIR=/path/to/build/bin MODEL=/path/model.gguf ./kv_kld_sweep.sh

# ---------------------------------------------------------------------------
# Config (all overridable via env)
# ---------------------------------------------------------------------------
BIN_DIR=${BIN_DIR:-/root/llama-master-regress/build/bin}
PPL_BIN=${PPL_BIN:-$BIN_DIR/llama-perplexity}
BENCH_BIN=${BENCH_BIN:-$BIN_DIR/llama-bench}
MODEL=${MODEL:-/root/turbo-logits-kld/Qwen3.6-27B-Q6_K-BOXMODEL.gguf}
DATASET=${DATASET:-/root/wikitext-2-raw/wiki.test.raw}
BASE_DIR=${BASE_DIR:-/root/turbo-logits-kld}
NGL=${NGL:-99}
FA=${FA:-on}
# Asymmetric K: if set, K is pinned to this type and the swept type is used for V
# only (e.g. KTYPE=q8_0 mirrors a fork's q8_0-K crutch). Unset = matched K=V.
# Cells are labeled "<KTYPE>:<type>" so they can't be mistaken for symmetric.
KTYPE=${KTYPE:-}
# Per-cell wall-clock cap (seconds). A cell exceeding this -> TIMEOUT, value "-".
CELL_TIMEOUT=${CELL_TIMEOUT:-10800}

# The "normal kinds" — upstream-standard GGML KV cache dtypes. Anything the build
# advertises that is NOT in this set is treated as a custom/special type to test.
# (This is the auto-detection filter the user asked for: subtract the standard set.)
STD_TYPES=${STD_TYPES:-"f32 f16 bf16 q8_0 q8_1 q4_0 q4_1 q5_0 q5_1 iq4_nl"}

# Context-depth tiers: "ctx:basefile:chunks". basefile/chunks only used by the KLD
# sweep (chunks is informational — the KLD consumer reads the whole base regardless).
# For the bench sweep only the ctx (used as -d depth) matters.
KV_TIERS=${KV_TIERS:-"\
2048:base_q6_f16kv_ctx2048_32ch.kld:32
8192:base_q6_f16kv_ctx8192_24ch.kld:24
16384:base_q6_f16kv_ctx16384_18ch.kld:18
32768:base_q6_f16kv_ctx32768_9ch.kld:9"}

# --shallow / KV_SHALLOW=1: keep only the FIRST (shallowest, fastest) context tier.
# A quick smoke check against the recorded baseline for that depth instead of running
# the full ladder. Set by the per-script --shallow flag or directly via env.
if [ "${KV_SHALLOW:-0}" = 1 ]; then
	KV_TIERS=$(printf '%s\n' "$KV_TIERS" | awk 'NF{print;exit}')
fi

# ---------------------------------------------------------------------------
# Auto-detect KV types from the binary's --help "allowed values" lists.
# Unions across EVERY "--cache-type*" flag (-ctk/-ctv plus the spec-draft
# -ctkd/-ctvd variants), since a fork may expose a type under only one of them.
# Handles each list wrapping across multiple indented continuation lines.
# ---------------------------------------------------------------------------
kv_enumerate_all() {
	"$PPL_BIN" --help 2>&1 | awk '
		# Any cache-type option line opens a fresh allowed-values block.
		/--cache-type/ { insec=1; cap=0 }
		insec && /allowed values:/ {
			s=$0; sub(/.*allowed values:[ \t]*/,"",s);
			gsub(/,/," ",s); printf "%s ", s;
			if ($0 ~ /,[ \t]*$/) cap=1; else { insec=0; cap=0 }
			next
		}
		cap {
			if ($0 ~ /^[ \t]*-/) { cap=0; insec=0; next }   # next CLI option -> block ended
			s=$0; gsub(/,/," ",s); printf "%s ", s;
			if ($0 !~ /,[ \t]*$/) { cap=0; insec=0 }        # last continuation line
		}
	'
}

# Print the special (custom) types: advertised minus STD_TYPES, deduped. One per line.
kv_special_types() {
	local std=" $STD_TYPES " t
	for t in $(kv_enumerate_all); do
		t="${t//[[:space:]]/}"
		[ -z "$t" ] && continue
		case "$std" in *" $t "*) continue ;; esac
		printf '%s\n' "$t"
	done | awk '!seen[$0]++'
}

# ---------------------------------------------------------------------------
# Classify a finished cell. Args: <rc> <logfile>. Echoes a status token.
#   OK | TIMEOUT | OOM | SEGV | KILLED | ABORT | SIG<n> | FAIL
# ---------------------------------------------------------------------------
kv_classify() {
	local rc=$1 log=$2
	if [ "$rc" = 124 ]; then echo TIMEOUT; return; fi
	if [ "$rc" -ge 128 ] 2>/dev/null; then
		local sig=$((rc - 128))
		case $sig in
			11) echo SEGV ;;
			9)  echo KILLED ;;
			6)  echo ABORT ;;
			*)  echo "SIG$sig" ;;
		esac
		return
	fi
	if [ "$rc" != 0 ]; then
		if grep -qiE 'out of memory|cudaMalloc|failed to allocate|CUDA error: out of memory|cudaErrorMemoryAllocation|unable to allocate' "$log" 2>/dev/null; then
			echo OOM
		else
			echo FAIL
		fi
		return
	fi
	echo OK
}

# First signed float AFTER the last colon on the first line matching a regex.
# (Reading past the last colon avoids picking up label numbers like "99.9%" in
# "99.9%   KLD:  16.531696".) Args: <logfile> <grep-ERE>. Empty if not found.
kv_num() {
	grep -m1 -E "$2" "$1" 2>/dev/null | sed 's/.*://' | grep -oE '[-]?[0-9]+\.[0-9]+' | head -1
}

# GPU name (for tagging results). Falls back gracefully off-box.
kv_gpu() {
	nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "unknown-gpu"
}

# Short build SHA if the binary lives in a git tree, else "?".
kv_build_sha() {
	git -C "$BIN_DIR" rev-parse --short HEAD 2>/dev/null || echo "?"
}

# ---------------------------------------------------------------------------
# Effective-BPW probe (anti-tomfoolery guard). A fork can silently substitute a
# fatter K/V type under a requested name (e.g. TheTom auto-upgrades K turbo->q8_0
# on GQA>=6) — see reference_thetom_turbo_layer_adaptive_trap. Static name->bpw
# tables can't catch this AND aren't build-agnostic (the same name has different
# bpw across forks). So we read the bytes the binary ACTUALLY allocates.
#
# llama.cpp prints, at load (verbose), one authoritative line:
#   llama_kv_cache: size = 28.12 MiB (2304 cells, 16 layers, ...), K (turbo3): 14.06 MiB, V (turbo3): 14.06 MiB
# The "K (TYPE): X MiB" fields are the REAL allocated type + size. We calibrate
# against an f16 probe at the same ctx (f16 = exactly 16 bits/elt), giving an
# exact, build-agnostic bits/elt:  bpw = 16 * type_MiB / f16_MiB.
# ---------------------------------------------------------------------------
BPW_PROBE_CTX=${BPW_PROBE_CTX:-2048}

# Emit the raw kv_cache size line for a K:V pair (empty on failure). Uses a 1-token
# llama-bench run at BPW_PROBE_CTX with -v so it loads fast and just allocates KV.
kv_probe_line() {  # ktype vtype
	timeout "${BPW_PROBE_TIMEOUT:-300}" env LD_LIBRARY_PATH="$BIN_DIR" "$BENCH_BIN" \
		-m "$MODEL" -ctk "$1" -ctv "$2" -fa 1 -ngl "$NGL" \
		-p 1 -n 1 -d "$BPW_PROBE_CTX" -r 1 -v 2>&1 \
		| grep -m1 -E 'llama_kv_cache: size =.*K \('
}

# Parse "K (TYPE)" / "V (TYPE)" and the MiB after them from a size line on stdin.
_kv_alloc_type() { sed -nE "s/.* $1 \(([^)]*)\):.*/\1/p"; }            # arg: K or V
_kv_alloc_mib()  { sed -nE "s/.* $1 \([^)]*\):[[:space:]]*([0-9.]+) MiB.*/\1/p"; }  # arg: K or V

# Build the per-type effective-BPW table for a sweep. Probes f16 once (calibration)
# then each requested type, writes <out_tsv>, and echoes a one-line compact map for
# meta.txt. Args: <out_tsv> <ktype_or_empty> <type...>. If a type's real K/V differs
# from what was requested, flag is "SUBST" (the smoking gun for a silent upgrade).
kv_build_bpw_tsv() {
	local out=$1 ktype=$2; shift 2
	printf 'req_k\treq_v\tact_k\tact_v\tbpw_k\tbpw_v\teff_bpw\tk_mib\tv_mib\tflag\n' > "$out"

	# Calibration: f16 K/V MiB at the probe ctx.
	local cal calk calv
	cal=$(kv_probe_line f16 f16)
	calk=$(printf '%s' "$cal" | _kv_alloc_mib K)
	calv=$(printf '%s' "$cal" | _kv_alloc_mib V)
	if [ -z "$calk" ] || [ -z "$calv" ]; then
		echo "f16\tf16\t-\t-\t-\t-\t-\t-\t-\tNOCAL" >> "$out"
		echo "bpw: (calibration probe failed — no effective-BPW guard this run)"
		return
	fi

	local map="bpw@ctx${BPW_PROBE_CTX}:"
	local t reqk line ak av km vm bk bv eff flag
	for t in "$@"; do
		reqk="${ktype:-$t}"
		line=$(kv_probe_line "$reqk" "$t")
		ak=$(printf '%s' "$line" | _kv_alloc_type K); av=$(printf '%s' "$line" | _kv_alloc_type V)
		km=$(printf '%s' "$line" | _kv_alloc_mib K);  vm=$(printf '%s' "$line" | _kv_alloc_mib V)
		if [ -z "$ak" ] || [ -z "$km" ]; then
			printf '%s\t%s\t-\t-\t-\t-\t-\t-\t-\tPROBEFAIL\n' "$reqk" "$t" >> "$out"
			map="$map ${reqk}:${t}=?"
			continue
		fi
		bk=$(awk -v m="$km" -v c="$calk" 'BEGIN{printf "%.3f", 16*m/c}')
		bv=$(awk -v m="$vm" -v c="$calv" 'BEGIN{printf "%.3f", 16*m/c}')
		eff=$(awk -v a="$bk" -v b="$bv" 'BEGIN{printf "%.3f", (a+b)/2}')
		flag=""
		[ "$ak" != "$reqk" ] && flag="SUBST(K:$reqk->$ak)"
		[ "$av" != "$t" ]    && flag="${flag:+$flag,}SUBST(V:$t->$av)"
		[ -z "$flag" ] && flag=OK
		printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$reqk" "$t" "$ak" "$av" "$bk" "$bv" "$eff" "$km" "$vm" "$flag" >> "$out"
		local lbl="${reqk}:${t}" mark=""; [ "$reqk" = "$t" ] && lbl="$t"
		[ "$flag" != OK ] && mark="!"
		map="$map ${lbl}=${eff}${mark}"
	done
	echo "$map"
}

# Render a bpw.tsv as a markdown table (for results.md). Arg: <bpw_tsv>.
kv_render_bpw_md() {
	[ -s "$1" ] || return
	echo "### Effective BPW (measured from actual KV allocation — substitution guard)"
	echo
	echo "| req K | req V | act K | act V | bpw K | bpw V | eff bpw | flag |"
	echo "|---|---|---|---|---|---|---|---|"
	awk -F'\t' 'NR>1{printf "| %s | %s | %s | %s | %s | %s | %s | %s |\n",$1,$2,$3,$4,$5,$6,$7,$10}' "$1"
	echo
}
