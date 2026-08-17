#!/usr/bin/env bash
# The flash-attention localisation test, second attempt.
#
# kv_xfork2.sh U1/U3 tried `-fa off` under `-sm tensor` and the server refused:
#   E llama_init_from_model: SPLIT_MODE_TENSOR requires flash_attn to be enabled
# So the FA arm cannot be run under tensor split at all on this build.
#
# It moves to LAYER split, which is legal with -fa off, and kv_xfork.sh T9 already
# supplies the matched control: `-sm layer -fa on -ctk q8_0 -ctv q8_0` collapsed 3/3.
# The collapse is split-independent on both forks, so layer split costs nothing here.
#
# F4 is the arm that decides whether the whole comparison is admissible: if `-fa off`
# is broken on this build for ANY codec, F1 proves nothing.
set -u

TOM=~/llama-cpp-turboquant/build/bin/llama-server
M=~/models/unsloth-Qwen3.8-27B-Q6_K.gguf
PORT=8092
OUT=~/xfork_fa
mkdir -p $OUT

[ -x "$TOM" ] || { echo "FATAL: no binary"; exit 1; }
[ -f "$M" ]   || { echo "FATAL: no model";  exit 1; }

echo "### FA LOCALISATION start $(date -Is)"
echo "### binary: $TOM"
echo "### version: $($TOM --version 2>&1 | head -1)"
echo

ready() {
  local name=$1
  for i in $(seq 1 100); do
    grep -q "GGML_ASSERT" $OUT/srv_$name.log 2>/dev/null && return 2
    pgrep -x llama-server >/dev/null || return 3
    r=$(curl -s --max-time 20 "http://127.0.0.1:$PORT/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{"messages":[{"role":"user","content":"hi"}],"n_predict":8,"cache_prompt":false}' 2>/dev/null)
    echo "$r" | grep -q '"choices"' && return 0
    sleep 4
  done
  return 1
}

probe() {
  local name=$1
  for i in 1 2 3; do
    curl -s --max-time 400 "http://127.0.0.1:$PORT/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Explain how a $i-stage CPU pipeline works, with examples.\"}],\"temperature\":1.0,\"top_p\":0.95,\"top_k\":20,\"n_predict\":512,\"cache_prompt\":false}" \
      > $OUT/resp_${name}_$i.json 2>/dev/null
    python3 - "$OUT/resp_${name}_$i.json" "$i" <<'PY'
import json,sys,collections
p,i = sys.argv[1], sys.argv[2]
try: d=json.load(open(p))
except Exception: print(f"  req{i} PARSE_FAIL"); raise SystemExit
if "choices" not in d: print(f"  req{i} ERR "+str(d)[:60]); raise SystemExit
m=d["choices"][0]["message"]; t=(m.get("content") or "")+(m.get("reasoning_content") or "")
if not t: print(f"  req{i} EMPTY"); raise SystemExit
run=mx=1; prev=""
for c in t:
    run = run+1 if c==prev else 1
    mx=max(mx,run); prev=c
bad = (mx>200 or len(set(t))<12)
top = collections.Counter(t).most_common(2)
print(f"  req{i} {'DEGENERATE' if bad else 'ok'} len={len(t)} maxrun={mx} uniq={len(set(t))}"
      + (f"  top={top}" if bad else ""))
PY
  done
}

# Wait for the port to actually be released. A fixed `sleep 5` is NOT enough after a
# hard abort: kv_xfork2.sh U6 launched while the core-dumping U5 still held 8092, failed
# with "couldn't bind HTTP server socket", and would have been reported as "q5_1 fails to
# start" -- a false codec finding produced entirely by the harness.
port_free() {
  for i in $(seq 1 40); do
    pgrep -x llama-server >/dev/null && { sleep 2; continue; }
    (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null && { exec 3<&- 3>&-; sleep 2; continue; }
    return 0
  done
  echo "  WARN: port $PORT still held after 80s"; return 1
}

run() {
  local name=$1; shift
  echo "### $name : $*"
  pkill -x llama-server 2>/dev/null; sleep 3; port_free
  TURBO_AUTO_ASYMMETRIC=0 setsid nohup $TOM -m $M -ngl 99 -c 16384 --jinja \
      --host 127.0.0.1 --port $PORT "$@" > $OUT/srv_$name.log 2>&1 < /dev/null &
  ready "$name"; rc=$?
  case $rc in
    0) probe "$name" ;;
    2) echo "  HARD ABORT"; grep -m2 "GGML_ASSERT" $OUT/srv_$name.log | sed 's/^/       /' ;;
    3) echo "  SERVER DIED"; grep -m3 -E "^.*E .*(requires|failed|error)" $OUT/srv_$name.log | sed 's/^/       /' ;;
    *) echo "  READY TIMEOUT"; tail -3 $OUT/srv_$name.log | sed 's/^/       /' ;;
  esac
  echo
}

# F4 FIRST: is `-fa off` usable at all on this build? If this is not clean, F1/F2/F3
# are uninterpretable and the run should be abandoned rather than reported.
run F4 -sm layer --spec-type draft-mtp -fa off -ctk f16  -ctv f16

# The test and its matched control, back to back on the same build and session.
run F1 -sm layer --spec-type draft-mtp -fa off -ctk q8_0 -ctv q8_0
run F2 -sm layer --spec-type draft-mtp -fa on  -ctk q8_0 -ctv q8_0    # expect collapse; = kv_xfork T9
run F3 -sm layer --spec-type draft-mtp -fa off -ctk q4_0 -ctv q4_0

# --- Re-run of the two stock-grid arms lost to the port race in kv_xfork2.sh -------
# U6 (q5_1) failed to bind because U5's core-dumping process still held the port; U7
# (iq4_nl) ran immediately after U6 and is suspect for the same reason. Neither result
# is admissible, so both are repeated here behind port_free().
run F5 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk q5_1   -ctv q5_1
run F6 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk iq4_nl -ctv iq4_nl

pkill -x llama-server 2>/dev/null
echo "### FA LOCALISATION DONE $(date -Is)"
