#!/usr/bin/env bash
# One-command pre-sale GPU test. Swap card -> boot -> run this -> get a report.
#
# Runs ON the bench rig (.76 live USB). Everything the card-1 test did, in one shot:
#   1. identity + VBIOS + VRAM size + PCIe link
#   2. clock tables vs reference  (catches mining BIOS caps)
#   3. connector enumeration      (catches disabled/faulty display outputs)
#   4. 30-min soak with telemetry (thermals, stability, throttling)
#   5. memtest_vulkan             (VRAM integrity -- the one that matters on ex-mining cards)
#
# WHY AUTO-DETECT THE CARD NODE: on card 1 the AMD GPU was card2 and the Intel iGPU was card1.
# That ordering is NOT stable across boots or across different GPUs, and hardcoding it would
# silently test the wrong device (or nothing). We find the discrete card by vendor ID and by
# excluding the boot/iGPU.
#
# Usage:  ./gpu_presale_test.sh [label]     e.g.  ./gpu_presale_test.sh rx580_card2
# Output: /tmp/<label>_report.txt  and  /tmp/<label>_soak.csv  (scp them to the control plane)
set -u
LABEL=${1:-card$(date +%H%M)}
DUR=${DUR:-1800}
REPORT=/tmp/${LABEL}_report.txt
CSV=/tmp/${LABEL}_soak.csv
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0}

exec > >(tee "$REPORT") 2>&1
echo "=== GPU PRE-SALE TEST: $LABEL — $(date -Is) ==="

# ---- locate the discrete GPU (NOT the iGPU) ----
CARD=""
for c in /sys/class/drm/card*/device/; do
	[ -f "$c/vendor" ] || continue
	v=$(cat "$c/vendor" 2>/dev/null)
	# 0x1002 = AMD/ATI, 0x10de = NVIDIA. Skip Intel (0x8086) which is the iGPU on this bench.
	if [ "$v" = "0x1002" ] || [ "$v" = "0x10de" ]; then
		# skip if it IS the boot vga AND an iGPU-class device; prefer a device with pp_dpm or nvidia
		CARD="$c"; break
	fi
done
[ -n "$CARD" ] || { echo "FATAL: no discrete AMD/NVIDIA GPU found"; exit 1; }
NODE=$(basename "$(dirname "$CARD")")          # e.g. card2
SLOT=$(basename "$(readlink -f "$CARD")")      # e.g. 0000:01:00.0
echo "discrete GPU: $NODE at $SLOT"

echo
echo "--- 1. IDENTITY ---"
lspci -vnn -s "${SLOT#0000:}" 2>/dev/null | head -3
echo "  vbios     : $(cat "$CARD/vbios_version" 2>/dev/null || echo n/a)"
VRAM=$(cat "$CARD/mem_info_vram_total" 2>/dev/null)
echo "  vram      : ${VRAM:-?} B ($(awk -v b="${VRAM:-0}" 'BEGIN{printf "%.0f", b/1073741824}') GB)"
echo "  driver    : $(lspci -k -s "${SLOT#0000:}" 2>/dev/null | grep -i 'driver in use' | cut -d: -f2)"

echo
echo "--- 2. CLOCK TABLES (mining-BIOS check) ---"
echo "  reference RX580: core ~1340MHz, mem 2000MHz, power 185W"
SMAX=$(grep -oE '[0-9]+Mhz' "$CARD/pp_dpm_sclk" 2>/dev/null | grep -oE '[0-9]+' | sort -n | tail -1)
MMAX=$(grep -oE '[0-9]+Mhz' "$CARD/pp_dpm_mclk" 2>/dev/null | grep -oE '[0-9]+' | sort -n | tail -1)
HW=$(echo "$CARD"hwmon/hwmon*/ | awk '{print $1}')
PCAP=$(cat "${HW}power1_cap" 2>/dev/null)
echo "  core max  : ${SMAX:-?} MHz"
echo "  mem max   : ${MMAX:-?} MHz"
echo "  power cap : $(awk -v p="${PCAP:-0}" 'BEGIN{printf "%.0f", p/1000000}') W"
echo "  pcie      : $(grep '\*' "$CARD/pp_dpm_pcie" 2>/dev/null | sed 's/^[0-9]*: //')"

echo
echo "--- 3. DISPLAY CONNECTORS ---"
echo "  (a port listed here EXISTS in the VBIOS; 'disconnected' just means nothing plugged in)"
for c in /sys/class/drm/${NODE}-*/; do
	[ -d "$c" ] || continue
	printf "  %-16s status=%-13s enabled=%s\n" "$(basename "$c")" \
		"$(cat "$c/status" 2>/dev/null)" "$(cat "$c/enabled" 2>/dev/null)"
done

echo
echo "--- 4. SOAK (${DUR}s) ---"
command -v glmark2-wayland >/dev/null || { echo "  FATAL: glmark2-wayland missing (pacman -S glmark2)"; exit 1; }
echo "t_s,sclk_mhz,mclk_mhz,temp_c,fan_rpm,power_w,busy_pct,vram_used_mb" > "$CSV"
nohup glmark2-wayland --run-forever > /tmp/${LABEL}_load.log 2>&1 &
LOAD=$!
sleep 3
t0=$(date +%s); crashes=0
while :; do
	el=$(( $(date +%s) - t0 )); [ "$el" -ge "$DUR" ] && break
	if ! kill -0 "$LOAD" 2>/dev/null; then
		crashes=$((crashes+1)); echo "  # LOAD DIED at ${el}s (restart #$crashes)"
		nohup glmark2-wayland --run-forever > /tmp/${LABEL}_load.log 2>&1 & LOAD=$!
	fi
	s=$(grep '\*' "$CARD/pp_dpm_sclk" 2>/dev/null | grep -oE '[0-9]+Mhz' | grep -oE '[0-9]+')
	m=$(grep '\*' "$CARD/pp_dpm_mclk" 2>/dev/null | grep -oE '[0-9]+Mhz' | grep -oE '[0-9]+')
	tc=$(cat "${HW}temp1_input" 2>/dev/null); tc=$((${tc:-0}/1000))
	fan=$(cat "${HW}fan1_input" 2>/dev/null)
	pw=$(cat "${HW}power1_input" 2>/dev/null); pw=$(awk -v p="${pw:-0}" 'BEGIN{printf "%.1f", p/1000000}')
	busy=$(cat "$CARD/gpu_busy_percent" 2>/dev/null)
	vu=$(cat "$CARD/mem_info_vram_used" 2>/dev/null); vu=$((${vu:-0}/1048576))
	echo "$el,$s,$m,$tc,${fan:-0},$pw,${busy:-0},$vu" >> "$CSV"
	sleep 10
done
kill "$LOAD" 2>/dev/null
awk -F, 'NR>1{n++; s+=$4; if($4>tm)tm=$4; if($2>sm)sm=$2; if($3>mm)mm=$3; if($6>pm)pm=$6; if($7>bm)bm=$7}
  END{printf "  rows=%d  temp mean=%.1fC max=%dC | sclk max=%d | mclk max=%d | power max=%.1fW | busy max=%d%%\n", n,s/n,tm,sm,mm,pm,bm}' "$CSV"
echo "  load_crashes: $crashes"
echo "  amdgpu errors (excluding benign PRT init line):"
sudo dmesg 2>/dev/null | grep -iE "amdgpu.*(error|fault|reset|timeout|hang)" | grep -v "PRT request" | tail -5 | sed 's/^/    /'

echo
echo "--- 5. VRAM INTEGRITY ---"
if command -v memtest_vulkan >/dev/null; then
	echo "1" | timeout 420 memtest_vulkan 2>&1 | grep -E "Standard 5-minute|iteration|PASS|FAIL|error" | tail -6 | sed 's/^/  /'
else
	echo "  SKIPPED: memtest_vulkan not installed (pacman -S memtest_vulkan)"
fi

echo
echo "=== DONE $(date -Is) ==="
echo "report: $REPORT"
echo "csv:    $CSV"
