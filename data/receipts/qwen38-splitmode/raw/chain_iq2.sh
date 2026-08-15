#!/usr/bin/env bash
# After the IQ3_XXS split x MTP ladder: fetch IQ2_M, then run the same ladder.
set -u
for i in $(seq 1 720); do
  grep -q "SPLIT x MTP DONE" /home/mark/mtp73/split_mtp.log 2>/dev/null && break
  sleep 30
done
grep -q "SPLIT x MTP DONE" /home/mark/mtp73/split_mtp.log 2>/dev/null || { echo "iq3 ladder did not finish"; exit 1; }
pgrep -x llama-server >/dev/null && { pkill -x llama-server; sleep 8; }
/home/mark/dl_iq2.sh || { echo "IQ2 download failed"; exit 1; }
s=$(stat -c%s /home/mark/models/Qwen3.8-27B-UD-IQ2_M.gguf 2>/dev/null || echo 0)
[ "$s" -gt 9000000000 ] || { echo "ABORT: IQ2_M looks truncated ($s)"; exit 1; }
sleep 10
exec /home/mark/mtp73/split_mtp_iq2.sh
