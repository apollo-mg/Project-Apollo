#!/bin/bash
# Wait for fit_lens.py, then apply the lens to BASE/LORA/LORA2 and run the registered analysis.
H=/mnt/TG_2TB/Projects/Apollo/data/receipts/jlens-idk; PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
until grep -q FIT_DONE $H/fit_lens.log 2>/dev/null; do kill -0 $(cat $H/fit_lens.pid) 2>/dev/null || { echo "fit died" >> $H/chain.log; exit 1; }; sleep 30; done
echo "apply start $(date '+%F %T')" >> $H/chain.log
$PY $H/apply_lens.py >> $H/chain.log 2>&1; echo "apply rc=$? $(date '+%F %T')" >> $H/chain.log
$PY $H/analyze_jlens.py > $H/analyze.log 2>&1; echo "analyze rc=$? $(date '+%F %T')" >> $H/chain.log
echo LENS_CHAIN_DONE >> $H/chain.log
