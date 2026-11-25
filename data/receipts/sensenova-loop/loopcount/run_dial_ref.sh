#!/bin/bash
# PREREG_LOOP_DIAL gate on .194: the reference implementation at 1 and 3 loops (config copies over the same weights).
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/sensenova-loop/loopcount; S=$H/raw/state_ref.log; log() { echo "$* $(date '+%F %T')" >> $S; }
HOST=mark@10.0.0.194; rx() { ssh -o BatchMode=yes $HOST "$1"; }
cd $R && tools/s194.sh on > /dev/null 2>&1
ok=0; for i in $(seq 90); do if timeout 8 ssh -o ConnectTimeout=5 -o BatchMode=yes $HOST true 2>/dev/null; then ok=$((ok+1)); [ $ok -ge 3 ] && break; else ok=0; fi; sleep 5; done
log ".194 up"
scp -q $R/data/receipts/sensenova-loop/ref_ppl.py $HOST:snlref/ref_ppl.py
for n in 1 3; do
  rx "set -e; B=~/AI/Models/sensenova-loop-9b-bf16; T=~/AI/Models/sensenova-loop-9b-bf16-loops$n; mkdir -p \$T; for f in \$B/*; do b=\$(basename \$f); [ \$b = config.json ] || ln -sf \$f \$T/\$b; done
    python3 -c \"import json; c=json.load(open('\$B/config.json')); c['loop_settings']['counts']=[$n]; c['loop_settings']['eval_count']=$n; json.dump(c, open('\$T/config.json','w'), indent=2)\"
    grep -A4 loop_settings \$T/config.json | tr -d ' \n'"
  echo >> $S; log "config loops$n written"
  rx "cd ~/snlref; ~/venv-snlref/bin/python -I ref_ppl.py ~/AI/Models/sensenova-loop-9b-bf16-loops$n wiki.test.raw ref_ppl_loops$n.json 20 > ref_ppl_loops$n.log 2>&1"
  log "reference loops$n rc=$? $(rx "tail -1 ~/snlref/ref_ppl_loops$n.log")"
  scp -q "$HOST:snlref/ref_ppl_loops$n.json" "$HOST:snlref/ref_ppl_loops$n.log" $H/raw/
done
rx "nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr '\n' ' '"; tools/s194.sh off > /dev/null 2>&1; log "REF_DONE; .194 off"
