#!/usr/bin/env bash
# buun's request: master @ b88daada9, tensor parallelism, WITH and WITHOUT
# GGML_CUDA_FORCE_GRAPHS=1, report the difference on Pascal (2x P100, sm_60).
#
# Uses the frozen probe (same prompt/budget as the 23.72 t/s dd48dd86b baseline) so all
# three builds are directly comparable. Coherence is gated before any t/s is reported.
# Also greps startup for the new "refuse shared-KV drafter on a tensor-split target" path,
# since this config runs --kv-unified + -sm tensor + --spec-type draft-mtp together.
set -u
R=~/buun_vbr
LOG=$R/graphs_ab.log
log(){ echo "[$(date +%F_%T)] $*" | tee -a "$LOG"; }

start_server() { # $1 = tag, $2 = "1" to force graphs
  pkill -f "buun_vbr/build/bin/llama-server" 2>/dev/null; sleep 6
  FORCE="$2" TAG="$1" python3 - <<'PY'
import json,os,subprocess
argv=json.load(open(os.path.expanduser("~/buun_vbr/argv_backup.json")))
env=dict(os.environ)
if os.environ.get("FORCE")=="1": env["GGML_CUDA_FORCE_GRAPHS"]="1"
else: env.pop("GGML_CUDA_FORCE_GRAPHS",None)
tag=os.environ["TAG"]
out=open(os.path.expanduser(f"~/buun_vbr/server_{tag}.log"),"w")
subprocess.Popen(argv,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,
                 stdin=subprocess.DEVNULL,env=env)
PY
  for i in $(seq 1 400); do
    curl -s -m 5 http://127.0.0.1:8082/health 2>/dev/null | grep -q '"status":"ok"' && return 0
    sleep 5
  done
  return 1
}

probe() { # $1 = tag  -> prints result lines
  SRV=$R/server_$1.log TAG="$1" python3 - <<'PY'
import json,os,re,statistics,urllib.request
SRV=os.environ["SRV"]; TAG=os.environ["TAG"]
P="Count from one to forty in words, comma separated. Then say DONE."
EVAL=re.compile(r"eval time =\s*[\d.]+ ms /\s*\d+ tokens \(\s*[\d.]+ ms per token,\s*([\d.]+) tokens per second")
DRAFT=re.compile(r"(?:draft acceptance|accept(?:ance)? rate|n_accept)[^0-9]*([\d.]+)",re.I)
tps=[];acc=[]
for i in range(4):
    off=os.path.getsize(SRV)
    b=json.dumps({"messages":[{"role":"user","content":P}],"max_tokens":3000,
                  "temperature":0.0,"stream":False}).encode()
    rq=urllib.request.Request("http://127.0.0.1:8082/v1/chat/completions",data=b,
                              headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(rq,timeout=1800) as r: d=json.loads(r.read())
    c=d["choices"][0]["message"].get("content") or ""
    with open(SRV,errors="ignore") as f: f.seek(off); seg=f.read()
    e=EVAL.findall(seg); a=DRAFT.findall(seg)
    ok=bool(c.strip()) and "forty" in c and "DONE" in c
    t=float(e[-1]) if e else None
    print(f"  {TAG} run{i+1}: coherent={ok} t/s={t} draft={a[-1] if a else '-'}")
    if ok and t: tps.append(t); acc.append(float(a[-1]) if a else 0)
if len(tps)>=2:
    print(f"  {TAG} RESULT n={len(tps)} mean={statistics.mean(tps):.2f} "
          f"sd={statistics.stdev(tps):.2f} draft={statistics.mean(acc):.4f}")
else:
    print(f"  {TAG} RESULT: NO COHERENT RUNS — no throughput reported")
PY
}

log "=== pulling master ==="
git -C $R checkout -q master && git -C $R pull --ff-only 2>&1 | tail -3 | tee -a "$LOG"
log "HEAD now: $(git -C $R log --oneline -1)"

log "=== building ==="
cmake --build $R/build -j 12 > $R/graphs_build.log 2>&1 || { log "BUILD FAILED"; tail -20 $R/graphs_build.log | tee -a "$LOG"; exit 1; }
log "build ok"

for LEG in nographs graphs; do
  F=0; [ "$LEG" = graphs ] && F=1
  log "--- leg $LEG (GGML_CUDA_FORCE_GRAPHS=$F) ---"
  if ! start_server "$LEG" "$F"; then
    log "$LEG: SERVER FAILED TO BECOME HEALTHY"
    grep -iE "refuse|shared-KV|drafter|error|assert" $R/server_$LEG.log | head -8 | tee -a "$LEG_ERR" | tee -a "$LOG"
    continue
  fi
  # surface the new refusal path and any graph-related notices
  grep -iE "refuse|shared-KV|graph|GGML_CUDA_FORCE_GRAPHS" $R/server_$LEG.log \
    | head -6 | sed 's/^/    startup: /' | tee -a "$LOG"
  probe "$LEG" | tee -a "$LOG"
done

log "=== done; baseline for reference: dd48dd86b = 23.72 t/s sd 0.03 draft 0.9035 ==="
touch $R/graphs.done
