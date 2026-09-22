#!/usr/bin/env bash
# Fully autonomous: wait for transfer, verify, launch both arms x5 reps, tear down, power off.
# Detached on purpose -- this outlives the session that started it.
set -u
A=/mnt/TG_2TB/Projects/Apollo/argus
R=/mnt/TG_2TB/Projects/Apollo
S=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
LOG=$A/runs/reps/orchestrator.log
exec >> "$LOG" 2>&1
echo "=== $(date -Iseconds) orchestrator start ==="

# 1. wait for the rsync to finish
while kill -0 "$(cat $S/hem_xfer.pid 2>/dev/null)" 2>/dev/null; do sleep 20; done
echo "transfer finished $(date -Iseconds)"

# 2. verify both files arrived at full size -- exact bytes, never rounded
for f in Qwen3.8-27B-Q5_K_M Altworld_Hemmingway-1-Q5_K_M; do
    sz=$(ssh -o ConnectTimeout=10 10.0.0.194 "stat -c %s ~/models/$f.gguf" 2>/dev/null)
    loc=$(stat -c %s /home/mark/Downloads/$f.gguf)
    [ "$sz" = "$loc" ] || { echo "ABORT: $f size mismatch remote=$sz local=$loc"; exit 1; }
    echo "verified $f = $sz bytes"
done

# 3. launch both servers
ssh 10.0.0.194 'setsid ~/start_arm.sh stock ~/models/Qwen3.8-27B-Q5_K_M.gguf 8084 0,1 0'
ssh 10.0.0.194 'setsid ~/start_arm.sh hemm  ~/models/Altworld_Hemmingway-1-Q5_K_M.gguf 8085 2,3 1'
ssh 10.0.0.194 'for f in argus_stock argus_hemm; do until grep -q "listening on" ~/$f.log 2>/dev/null || grep -qiE "error|abort" ~/$f.log 2>/dev/null; do sleep 4; done; done'
for p in 8084 8085; do
    curl -s -m 120 "http://10.0.0.194:$p/v1/chat/completions" -H 'Content-Type: application/json' \
      -d '{"messages":[{"role":"user","content":"say ready"}],"max_tokens":128,"temperature":0}' \
      | head -c 200; echo " <- port $p"
done

# 4. point fixture B at Hemmingway, A at stock Q5
python3 - <<'PYEOF'
import re
for fx,url,mdl in (("pilotA","8084","/home/mark/models/Qwen3.8-27B-Q5_K_M.gguf"),
                   ("pilotB","8085","/home/mark/models/Altworld_Hemmingway-1-Q5_K_M.gguf")):
    p=f"/mnt/TG_2TB/Projects/Apollo/argus/fixtures/{fx}/agent-home/config.yaml"
    s=open(p).read()
    s=re.sub(r"base_url: http://10\.0\.0\.194:\d+/v1", f"base_url: http://10.0.0.194:{url}/v1", s)
    s=re.sub(r"default: /home/mark/[^\n]+\.gguf", f"default: {mdl}", s)
    open(p,"w").write(s)
    print(f"{fx} -> :{url} {mdl.split('/')[-1]}")
PYEOF

# 5. five reps per arm, concurrent
"$R/tools/benchmark_lock.sh" acquire "hemmingway vs stock, 5 reps"
"$A/run_reps_arm.sh" A pilotA 5 & PA=$!
"$A/run_reps_arm.sh" B pilotB 5 & PB=$!
wait $PA $PB
echo "=== both arms complete $(date -Iseconds) ==="
wc -l "$A/runs/reps/A.jsonl" "$A/runs/reps/B.jsonl"

# 6. tear down AND power off -- AFM-40: nvidia-smi 0 MiB is not "the node is off"
"$R/tools/pilot_teardown.sh" --poweroff
echo "=== $(date -Iseconds) orchestrator done ==="
