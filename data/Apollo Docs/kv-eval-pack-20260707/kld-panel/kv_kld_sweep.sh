#!/bin/bash
# kv_kld_sweep.sh — KLD/PPL regression of custom KV-cache types vs logit bases.
#
# Matrix: {auto-detected special KV types} x {context tiers}. K and V are set to the
# same type (matched K=V). Each cell runs llama-perplexity --kl-divergence against the
# tier's logit base and records Mean/Median/tail KLD, PPL(Q), ln-ratio, RMS Δp, same-top-p.
#
# Failures (OOM / segfault / timeout / other) are caught and recorded as "-" so one bad
# cell never sinks the sweep. Resumable: a cell already marked OK in results.tsv is skipped.
#
# Usage:
#   ./kv_kld_sweep.sh [run_dir]
#   ./kv_kld_sweep.sh --shallow                       # only the first (shallowest) tier
#   TYPES="turbo3 turbo3_tcq" ./kv_kld_sweep.sh      # restrict types
#   (override BIN_DIR/MODEL/BASE_DIR/DATASET/KV_TIERS/CELL_TIMEOUT via env — see kv_common.sh)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Strip recognized flags before positional handling. --shallow restricts the run to
# the first context tier (fast smoke vs. the full ladder); see kv_common.sh.
_args=()
for _a in "$@"; do
	case "$_a" in
		--shallow) export KV_SHALLOW=1 ;;
		*) _args+=("$_a") ;;
	esac
done
if [ ${#_args[@]} -gt 0 ]; then set -- "${_args[@]}"; else set --; fi

. "$HERE/kv_common.sh"

RUN_DIR=${1:-${RUN_DIR:-/root/kv-regress/kld_$(date +%Y%m%d_%H%M%S)}}
mkdir -p "$RUN_DIR/logs"
TSV="$RUN_DIR/results.tsv"
MD="$RUN_DIR/results.md"
META="$RUN_DIR/meta.txt"
CURRENT="$RUN_DIR/current"

TYPES=${TYPES:-$(kv_special_types | tr '\n' ' ')}

{
	echo "kind=KLD/PPL"
	echo "started=$(date -u +%FT%TZ)"
	echo "gpu=$(kv_gpu)"
	echo "build_sha=$(kv_build_sha)"
	echo "model=$MODEL"
	echo "dataset=$DATASET"
	echo "base_dir=$BASE_DIR"
	echo "types=$TYPES"
	echo "ktype=${KTYPE:-<matched K=V>}"
	echo "tiers=$(echo "$KV_TIERS" | awk -F: '{print $1}' | tr '\n' ' ')"
	echo "cell_timeout=$CELL_TIMEOUT"
} > "$META"

# Effective-BPW guard: measure what each type ACTUALLY allocates (catches silent
# K/V substitution like TheTom's q8_0-K auto-upgrade). One-time probe per type.
BPW_TSV="$RUN_DIR/bpw.tsv"
echo "Probing effective BPW (anti-substitution guard) ..."
BPW_MAP=$(kv_build_bpw_tsv "$BPW_TSV" "${KTYPE:-}" $TYPES)
echo "$BPW_MAP" >> "$META"
echo "  $BPW_MAP"

# TSV header (written once)
if [ ! -s "$TSV" ]; then
	printf 'type\tctx\tchunks\tstatus\tmean_kld\tkld_ci\tmedian_kld\tp999_kld\tmax_kld\tppl_q\tln_ratio\trms_dp\tsame_top_p\tsecs\n' > "$TSV"
fi

cell_done_ok() {  # type ctx -> 0 if an OK row already exists
	awk -F'\t' -v t="$1" -v c="$2" 'NR>1 && $1==t && $2==c && $4=="OK"{found=1} END{exit !found}' "$TSV"
}

render_md() {
	{
		echo "# KV-cache KLD/PPL sweep"
		echo
		sed 's/^/    /' "$META"
		echo
		kv_render_bpw_md "$BPW_TSV"
		echo "| type | ctx | status | mean KLD | ±ci | median KLD | 99.9% KLD | max KLD | PPL(Q) | ln(Q/base) | RMS Δp% | same-top-p% | secs |"
		echo "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
		awk -F'\t' 'NR>1{printf "| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |\n",$1,$2,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14}' "$TSV"
	} > "$MD"
}

run_cell() {
	local type=$1 ctx=$2 base=$3 chunks=$4
	# Asymmetric support: if KTYPE is set, K is fixed to KTYPE and the swept
	# `type` becomes V only. The stored/displayed label encodes the real K:V pair
	# so it can't be mistaken for a symmetric cell (mirrors forks that pin K=q8_0).
	local ktype="${KTYPE:-$type}"
	local label="$type"; [ -n "${KTYPE:-}" ] && label="${KTYPE}:$type"
	local log="$RUN_DIR/logs/${label//:/_}_ctx${ctx}.log"
	local basepath="$BASE_DIR/$base"

	if [ ! -f "$basepath" ]; then
		printf '%s\t%s\t%s\t%s\t-\t-\t-\t-\t-\t-\t-\t-\t-\t0\n' "$label" "$ctx" "$chunks" "NOBASE" >> "$TSV"
		echo "  [skip] $label ctx=$ctx — base missing: $basepath"
		return
	fi

	echo "$label ctx=$ctx started=$(date -u +%FT%TZ) log=$log" > "$CURRENT"
	local t0 t1 rc status
	t0=$(date +%s)
	timeout "$CELL_TIMEOUT" env LD_LIBRARY_PATH="$BIN_DIR" "$PPL_BIN" \
		-m "$MODEL" -f "$DATASET" \
		--kl-divergence-base "$basepath" --kl-divergence \
		-ctk "$ktype" -ctv "$type" -fa "$FA" -c "$ctx" --chunks "$chunks" -ngl "$NGL" \
		> "$log" 2>&1
	rc=$?
	t1=$(date +%s)
	status=$(kv_classify "$rc" "$log")

	local mean ci median p999 maxk pplq lnr rms stp
	if [ "$status" = OK ]; then
		mean=$(kv_num   "$log" 'Mean[[:space:]]+KLD:')
		ci=$(grep -m1 -E 'Mean[[:space:]]+KLD:' "$log" | grep -oE '[0-9]+\.[0-9]+' | sed -n 2p)
		median=$(kv_num "$log" 'Median[[:space:]]+KLD:')
		p999=$(kv_num   "$log" '99\.9%[[:space:]]+KLD:')
		maxk=$(kv_num   "$log" 'Maximum[[:space:]]+KLD:')
		pplq=$(kv_num   "$log" 'Mean PPL\(Q\)')
		lnr=$(kv_num    "$log" 'Mean ln\(PPL\(Q\)/PPL\(base\)\)')
		rms=$(kv_num    "$log" 'RMS.*:')
		stp=$(kv_num    "$log" 'Same top p:')
	else
		mean=- ci=- median=- p999=- maxk=- pplq=- lnr=- rms=- stp=-
	fi
	: "${mean:=-}" "${ci:=-}" "${median:=-}" "${p999:=-}" "${maxk:=-}" "${pplq:=-}" "${lnr:=-}" "${rms:=-}" "${stp:=-}"

	printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
		"$label" "$ctx" "$chunks" "$status" "$mean" "$ci" "$median" "$p999" "$maxk" "$pplq" "$lnr" "$rms" "$stp" "$((t1 - t0))" >> "$TSV"
	render_md
	echo "  [$status] $label ctx=$ctx  meanKLD=$mean  PPL=$pplq  ($((t1 - t0))s)"
}

echo "KLD/PPL sweep -> $RUN_DIR"
echo "types: $TYPES"
for type in $TYPES; do
	label="$type"; [ -n "${KTYPE:-}" ] && label="${KTYPE}:$type"
	while IFS=: read -r ctx base chunks; do
		[ -z "$ctx" ] && continue
		if cell_done_ok "$label" "$ctx"; then
			echo "  [done] $label ctx=$ctx (resume skip)"
			continue
		fi
		run_cell "$type" "$ctx" "$base" "$chunks"
	done <<< "$KV_TIERS"
done

rm -f "$CURRENT"
echo "finished=$(date -u +%FT%TZ)" >> "$META"
render_md
echo "DONE. Results: $MD"
