#!/usr/bin/env bash
# Bring the H10's 512GB NAND half into service on .73 and get the model off the USB volume.
# Baseline to beat: 442s model load from /run/media/mark/Ventoy1 (~51 MB/s).
# Owner confirmed no data to preserve on nvme1n1 (carried an isw_raid_member signature from a
# prior Intel RST array). Source files are COPIED, not moved — Ventoy copy stays as fallback
# until the new path is proven by a coherence probe.
set -u
LOG=~/buun_vbr/nvme_setup.log
log(){ echo "[$(date +%F_%T)] $*" | tee -a "$LOG"; }

DEV=/dev/nvme1n1
SRC_MODEL="/mnt/HDD/Models/Qwen 3.6/Qwen3.6-27B-Q6_K-MTP.gguf"
SRC_MMPROJ="/mnt/HDD/Models/Qwen 3.6/mmproj-F16.gguf"

log "=== safety checks ==="
if mount | grep -q "$DEV"; then log "ABORT: $DEV has a mounted partition"; exit 1; fi
if pgrep -f "[l]lama-server" >/dev/null; then log "stopping llama-server"; pgrep -f "[l]lama-server" | while read p; do kill -9 "$p"; done; sleep 5; fi
[ -f "$SRC_MODEL" ] || { log "ABORT: source model missing"; exit 1; }

log "=== wiping RST metadata + partitioning ==="
sudo wipefs -a "$DEV" >> "$LOG" 2>&1
sudo parted -s "$DEV" mklabel gpt >> "$LOG" 2>&1
sudo parted -s -a opt "$DEV" mkpart primary ext4 0% 100% >> "$LOG" 2>&1
sleep 3
sudo mkfs.ext4 -F -L models -m 0 "${DEV}p1" >> "$LOG" 2>&1 || { log "ABORT: mkfs failed"; exit 1; }
UUID=$(sudo blkid -s UUID -o value "${DEV}p1")
log "new filesystem UUID = $UUID"

sudo mkdir -p /mnt/models
sudo mount "${DEV}p1" /mnt/models || { log "ABORT: mount failed"; exit 1; }
sudo chown mark:mark /mnt/models
log "mounted: $(df -h /mnt/models | tail -1)"

log "=== fstab: add models, restore swap WITH nofail ==="
sudo cp /etc/fstab /etc/fstab.bak.$(date +%s)
grep -q "/mnt/models" /etc/fstab || \
  echo "UUID=$UUID /mnt/models ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab > /dev/null
# re-enable the optane swapfile, this time with nofail so a missing drive can't stall boot
sudo sed -i 's|^#/mnt/optane/swapfile none swap sw,pri=100 0 0|/mnt/optane/swapfile none swap sw,pri=100,nofail 0 0|' /etc/fstab
sudo swapon /mnt/optane/swapfile 2>>"$LOG" && log "swap restored: $(swapon --show | tail -1)" || log "swap restore FAILED (check manually)"

log "=== copying model (22.6GB from USB — expect ~8 min) ==="
T0=$(date +%s)
cp "$SRC_MODEL" /mnt/models/ || { log "ABORT: model copy failed"; exit 1; }
cp "$SRC_MMPROJ" /mnt/models/ || log "WARN: mmproj copy failed"
sync
T1=$(date +%s)
log "copy done in $((T1-T0))s"
log "sizes: src=$(stat -c%s "$SRC_MODEL") dst=$(stat -c%s /mnt/models/Qwen3.6-27B-Q6_K-MTP.gguf)"
[ "$(stat -c%s "$SRC_MODEL")" = "$(stat -c%s /mnt/models/Qwen3.6-27B-Q6_K-MTP.gguf)" ] \
  && log "size match OK" || { log "ABORT: size mismatch"; exit 1; }

log "=== rewriting argv to the new paths ==="
python3 - <<'PY' | tee -a "$LOG"
import json,os
p=os.path.expanduser("~/buun_vbr/argv_backup.json")
argv=json.load(open(p))
new=[]
for a in argv:
    if a.endswith("Qwen3.6-27B-Q6_K-MTP.gguf"): a="/mnt/models/Qwen3.6-27B-Q6_K-MTP.gguf"
    elif a.endswith("mmproj-F16.gguf") and os.path.exists("/mnt/models/mmproj-F16.gguf"):
        a="/mnt/models/mmproj-F16.gguf"
    new.append(a)
json.dump(new,open(os.path.expanduser("~/buun_vbr/argv_nvme.json"),"w"),indent=1)
print("argv rewritten -> argv_nvme.json")
PY

log "=== restarting server from NVMe, timing the load ==="
T2=$(date +%s)
python3 - <<'PY'
import json,os,subprocess
argv=json.load(open(os.path.expanduser("~/buun_vbr/argv_nvme.json")))
out=open(os.path.expanduser("~/buun_vbr/server_nvme.log"),"w")
subprocess.Popen(argv,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,
                 stdin=subprocess.DEVNULL)
PY
for i in $(seq 1 400); do
  curl -s -m 5 http://127.0.0.1:8082/health 2>/dev/null | grep -q '"status":"ok"' && break
  sleep 2
done
T3=$(date +%s)
if curl -s -m 5 http://127.0.0.1:8082/health | grep -q '"status":"ok"'; then
  log "LOAD TIME FROM NVMe: $((T3-T2))s   (USB baseline was 442s)"
else
  log "server did not come up — check server_nvme.log"; exit 2
fi

log "=== coherence probe (never trust a config without reading the text) ==="
curl -s -m 900 http://127.0.0.1:8082/v1/chat/completions -H 'Content-Type: application/json' \
 -d '{"messages":[{"role":"user","content":"Count from one to forty in words, comma separated. Then say DONE."}],"max_tokens":3000,"temperature":0}' \
 | python3 -c 'import json,sys; d=json.load(sys.stdin); c=d["choices"][0]["message"].get("content") or ""; print("COHERENT" if ("forty" in c and "DONE" in c) else "SUSPECT"); print("first200:",repr(c[:200]))' \
 | tee -a "$LOG"

log "=== final state ==="
df -h /mnt/models /mnt/optane 2>/dev/null | tee -a "$LOG"
swapon --show | tee -a "$LOG"
log "Ventoy copy left in place as fallback — delete once you are happy"
touch ~/buun_vbr/nvme_setup.done
