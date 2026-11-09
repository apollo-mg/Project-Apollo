#!/usr/bin/env bash
# PREREG_SCI_DISTILL.md, on the desktop. Waits for both downloads, converts both checkpoints to Q8_0 with one converter
# (llama.cpp 67107ac34f, --no-mtp), records the tensor map, stages both on .194 (hash checked), then:
#   M1:   Q35B on GPU 0 (:8190) and DSV9 on GPU 2 (:8191), -np 1, thinking off, greedy (run_main.py)
#   GPQA: Q35B on GPUs 0+1 (:8190, :8191), DSV9 on GPUs 2+3 (:8192, :8193), -np 4, thinking on, rounds 1-4,
#         no request after a 24 h deadline; when DSV9 has its 4 rounds, GPUs 2+3 restart as Q35B and join that arm.
# Gates before any row: model identity, flags, M1 and GPQA token gates, smokes. Analysis; .194 powered off.
# Resumable: run_main.py and run_gpqa.py skip what is already written.
set -uo pipefail
R=/mnt/TG_2TB/Projects/Apollo; SD=$R/data/receipts/sci-distill; QA=$R/data/receipts/quant-abstention; PY=$R/venv_cachyos/bin/python3
LC=$R/engines/llama_cpp_67107ac; SRC_B=/mnt/TG_2TB/AI/Models/qwen35-9b; SRC_F=/mnt/TG_2TB/AI/Models/dsv4p-qwen35-9b
OUTD=/mnt/TG_2TB/AI/Models/sci-distill-gguf; GB=$OUTD/Qwen3.5-9B-Q8_0.gguf; GF=$OUTD/DSV4P-Qwen3.5-9B-Q8_0.gguf
H=10.0.0.194; RD='~/AI/Models/sci-distill'; BIN='~/llama.cpp-67107ac/build_sm60/bin/llama-server'
PRIV=/mnt/TG_2TB/AI/private/sci-distill; RAW=$SD/raw; LOG=$RAW/chain.log
M1FLAGS="-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off --jinja --cache-ram 0 --host 0.0.0.0"
GQFLAGS="-ngl 99 -c 131072 -ctk f16 -ctv f16 -np 4 --kv-unified -fit off --jinja --cache-ram 0 --host 0.0.0.0"
mkdir -p "$RAW/logs" "$PRIV" "$OUTD"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
finish() { stopall; timeout 120 "$R/tools/s194.sh" off >> "$LOG" 2>&1; log "== DONE (${1:-0})"; exit "${1:-0}"; }
export HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1

# 1. downloads, conversion, tensor map
for u in q35-base-dl q35-ft-dl; do while [ "$(systemctl --user show $u -p ActiveState --value 2>/dev/null)" = active ]; do sleep 30; done; done
for d in "$SRC_B" "$SRC_F"; do tail -n 1 "$d/download.log" | grep -q "ALL OK$" || { log "download not ALL OK: $d"; exit 1; }; done
conv() {   # conv SRC OUT
  [ -s "$2" ] && return 0; log "converting $(basename "$1") -> $(basename "$2")"
  (cd /tmp && "$PY" "$LC/convert_hf_to_gguf.py" "$1" --outtype q8_0 --no-mtp --outfile "$2" > "$2.convert.log" 2>&1) \
    || { log "convert failed: $(tail -n 2 "$2.convert.log" | tr '\n' ' ')"; mv -f "$2" "$2.failed" 2>/dev/null; return 1; }
}
conv "$SRC_B" "$GB" && conv "$SRC_F" "$GF" || exit 1
SHA_B=$(sha256sum "$GB" | cut -d' ' -f1); SHA_F=$(sha256sum "$GF" | cut -d' ' -f1)
log "Q35B $(stat -c %s "$GB") B sha256 $SHA_B | DSV9 $(stat -c %s "$GF") B sha256 $SHA_F"
"$PY" -I "$R/data/receipts/arete/tensor_map.py" "$LC/gguf-py" "$GF" "$GB" > "$SD/tensor_map.txt" 2>&1; log "tensor map: $(sed -n 3p "$SD/tensor_map.txt")"

# 2. .194 up and idle, files staged
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$H" true 2>/dev/null; then "$R/tools/s194.sh" on >> "$LOG" 2>&1 || { log "ABORT: .194 did not come up"; exit 1; }; fi
ssh "$H" 'pgrep -x llama-server >/dev/null' && { log "ABORT: a llama-server is already running on .194"; exit 1; }
ssh "$H" "mkdir -p $RD ~/sci"
for spec in "$GB|$SHA_B" "$GF|$SHA_F"; do IFS='|' read -r f want <<< "$spec"
  got=$(ssh "$H" "sha256sum $RD/$(basename "$f") 2>/dev/null" | cut -d' ' -f1)
  [ "$got" = "$want" ] || { scp -q "$f" "$H:AI/Models/sci-distill/" || { log "ABORT: scp $f"; finish 1; }
    got=$(ssh "$H" "sha256sum $RD/$(basename "$f")" | cut -d' ' -f1); [ "$got" = "$want" ] || { log "ABORT: HASH MISMATCH $f on .194"; finish 1; }; }
done
log "both files verified on .194; GPUs: $(ssh "$H" 'nvidia-smi --query-gpu=index,power.limit,clocks.applications.graphics --format=csv,noheader' | tr '\n' ';')"

# server helpers: one GPU per server, PID recorded at launch, killed only after readlink confirms it
start() {  # start LABEL FILE GPU PORT FLAGS
  ssh "$H" "CUDA_VISIBLE_DEVICES=$3 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $RD/$(basename "$2") $5 --port $4 > ~/sci/srv_$4.log 2>&1 < /dev/null & echo \$! > ~/sci/srv_$4.pid"
  local i up=0; for i in $(seq 1 120); do sleep 5; curl -sf -m 5 "http://$H:$4/health" >/dev/null && { up=1; break; }
    ssh "$H" "kill -0 \$(cat ~/sci/srv_$4.pid) 2>/dev/null" || break; done
  [ $up = 1 ] || { log "ABORT: $1 on :$4 not healthy: $(ssh "$H" "tail -n 2 ~/sci/srv_$4.log")"; return 1; }
  local mp; mp=$(curl -s -m 5 "http://$H:$4/props" | "$PY" -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$(basename "$2")" ] || { log "ABORT: $1 :$4 WRONG SERVER: $mp"; return 1; }
  ssh "$H" "tr '\0' ' ' < /proc/\$(cat ~/sci/srv_$4.pid)/cmdline" | grep -q -- "$5" || { log "ABORT: $1 :$4 flags not on the command line"; return 1; }
  log "$1 up on GPU $3 :$4 ($(basename "$mp")), $(ssh "$H" "nvidia-smi -i $3 --query-gpu=memory.used --format=csv,noheader")"
}
stop() {   # stop PORT
  ssh "$H" "P=\$(cat ~/sci/srv_$1.pid 2>/dev/null); [ -n \"\$P\" ] && [ \"\$(readlink /proc/\$P/exe)\" = \"\$HOME/llama.cpp-67107ac/build_sm60/bin/llama-server\" ] && kill \$P && timeout 60 tail --pid=\$P -f /dev/null; rm -f ~/sci/srv_$1.pid"
}
stopall() { for p in 8190 8191 8192 8193; do stop $p; done; }
smoke() {  # smoke PORT THINKING: off -> content and no reasoning (greedy); on -> both (the GPQA sampling, as greedy thinking can loop)
  local s='"temperature":0'; [ "$2" = true ] && s='"temperature":1.0,"top_p":0.95,"top_k":20,"min_p":0,"presence_penalty":1.5,"seed":1'
  curl -s -m 1800 "http://$H:$1/v1/chat/completions" -H 'Content-Type: application/json' -d "{\"messages\":[{\"role\":\"user\",\"content\":\"What is 17*19? Answer briefly.\"}],$s,\"max_tokens\":8192,\"cache_prompt\":false,\"chat_template_kwargs\":{\"enable_thinking\":$2}}" \
  | python3 -c "import sys,json; m=json.load(sys.stdin)['choices'][0]['message']; c=len(m.get('content') or ''); r=len(m.get('reasoning_content') or ''); print('content',c,'reasoning',r); sys.exit(0 if c and ((r > 0) == ('$2' == 'true')) else 1)"
}

# 3. M1 (thinking off, greedy), both arms at once, with the gates
start Q35B "$GB" 0 8190 "$M1FLAGS" && start DSV9 "$GF" 2 8191 "$M1FLAGS" || finish 1
mb=$("$PY" "$QA/../ds41-h2h/prompt_gate.py" "http://$H:8190"); mf=$("$PY" "$QA/../ds41-h2h/prompt_gate.py" "http://$H:8191")
gb=$(cd "$SD" && "$PY" gpqa_gate.py "http://$H:8190"); gf=$(cd "$SD" && "$PY" gpqa_gate.py "http://$H:8191")
log "M1 gate Q35B $mb | DSV9 $mf"; log "GPQA gate Q35B $gb | DSV9 $gf"
[ -n "$mb" ] && [ "$mb" = "$mf" ] && [ -n "$gb" ] && [ "$gb" = "$gf" ] || { log "ABORT: TOKEN GATE DIFFERS -- registered contingency (reconvert DSV9 with the base tokenizer) needed"; finish 1; }
for p in 8190 8191; do r=$(smoke $p false) || { log "ABORT: :$p thinking-off smoke failed: $r"; finish 1; }; log ":$p smoke off OK: $r"
  r=$(smoke $p true) || { log "ABORT: :$p thinking-on smoke failed: $r"; finish 1; }; log ":$p smoke on OK: $r"; done
meta() { "$PY" -c 'import json,sys; print(json.dumps(dict(zip(["arm","model","sha256","commit","flags","env","host","prereg"], sys.argv[1:]))))' \
  "$1" "$2" "$3" 67107ac34f "$4" "CUDA_VISIBLE_DEVICES=$5 GGML_CUDA_ALLREDUCE=internal" ".194 single P100" PREREG_SCI_DISTILL.md; }
m1() {     # m1 ARM PORT MODEL SHA GPU EXPECT_HEADER_FILE
  local tail var; var=$("$PY" -c 'import json,sys; print(json.dumps(json.loads(open(sys.argv[1]).readline())["variant_ids"]))' "$6")
  tail=$("$PY" -c 'import json,sys; sys.stdout.write(json.loads(open(sys.argv[1]).readline())["render_tail"])' "$6"; printf x); tail=${tail%x}
  (cd "$QA" && "$PY" run_main.py --url "http://$H:$2" --arm "$1" --usage --max-tokens 1024 --timeout 600 \
     --meta "$(meta "$1" "$3" "$4" "$M1FLAGS --port $2" "$5")" --expect-variants "$var" --expect-render-tail "$tail") >> "$RAW/logs/m1_$1.log" 2>&1
}
log "M1: Q35B against the stored Qwen3.6 base's ids and render tail"
m1 Q35B 8190 "Qwen3.5-9B Q8_0 (our conversion)" "$SHA_B" 0 "$QA/raw/main_Q36B.jsonl"; rc=$?
if [ ! -s "$QA/raw/main_Q35B.jsonl" ] && grep -q "differ.* from the ceiling" "$RAW/logs/m1_Q35B.log"; then
  log "Qwen3.5 ids or tail differ from Qwen3.6's ($(grep 'differ' "$RAW/logs/m1_Q35B.log" | tail -n 1 | cut -c1-160)); registered fallback: Q35B's own"
  (cd "$QA" && "$PY" run_main.py --url "http://$H:8190" --arm Q35B --usage --max-tokens 1024 --timeout 600 \
     --meta "$(meta Q35B "Qwen3.5-9B Q8_0 (our conversion)" "$SHA_B" "$M1FLAGS --port 8190" 0)") >> "$RAW/logs/m1_Q35B.log" 2>&1; rc=$?
fi
log "Q35B M1 exit $rc ($(( $(wc -l < "$QA/raw/main_Q35B.jsonl") - 1 )) rows)"
m1 DSV9 8191 "DeepSeek-V4-Pro-Qwen3.5-9B Q8_0 (our conversion)" "$SHA_F" 2 "$QA/raw/main_Q35B.jsonl"
log "DSV9 M1 exit $? ($(( $(wc -l < "$QA/raw/main_DSV9.jsonl" 2>/dev/null || echo 1) - 1 )) rows)"
stop 8190; stop 8191

# 4. GPQA (thinking on), in rounds
start Q35B "$GB" 0 8190 "$GQFLAGS" && start Q35B "$GB" 1 8191 "$GQFLAGS" && start DSV9 "$GF" 2 8192 "$GQFLAGS" && start DSV9 "$GF" 3 8193 "$GQFLAGS" || finish 1
printf 'http://%s:8190\nhttp://%s:8191\n' $H $H > "$RAW/urls_Q35B.txt"; printf 'http://%s:8192\nhttp://%s:8193\n' $H $H > "$RAW/urls_DSV9.txt"
DEADLINE=$(( $(date +%s) + 86400 )); log "GPQA start; deadline $(date -d @$DEADLINE '+%F %T')"
gq() {     # gq ARM SHA FILE
  (cd "$SD" && "$PY" run_gpqa.py --arm "$1" --urls "@$RAW/urls_$1.txt" --rounds 1-4 --slots 4 --max-tokens 30000 --deadline "$DEADLINE" \
     --public "$RAW/gpqa_$1.jsonl" --private "$PRIV/gpqa_$1.jsonl" \
     --meta "$(meta "$1" "$3" "$2" "$GQFLAGS" "one per server")") >> "$RAW/logs/gpqa_$1.log" 2>&1
}
rows() { echo $(( $(wc -l < "$RAW/gpqa_$1.jsonl" 2>/dev/null || echo 1) - 1 )); }
gq Q35B "$SHA_B" "$(basename "$GB")" & PB=$!
gq DSV9 "$SHA_F" "$(basename "$GF")"
[ "$(rows DSV9)" -lt 792 ] && [ "$(date +%s)" -lt "$DEADLINE" ] && { log "DSV9: $(rows DSV9) rows, retrying the missing"; gq DSV9 "$SHA_F" "$(basename "$GF")"; }
log "DSV9 GPQA done: $(rows DSV9) rows"
if [ "$(rows DSV9)" -ge 792 ] && kill -0 $PB 2>/dev/null; then
  stop 8192; stop 8193
  if start Q35B "$GB" 2 8192 "$GQFLAGS" && start Q35B "$GB" 3 8193 "$GQFLAGS"; then
    printf 'http://%s:8192\nhttp://%s:8193\n' $H $H >> "$RAW/urls_Q35B.txt"; log "GPUs 2+3 joined the Q35B arm (progress rule)"
  else log "GPUs 2+3 did not come back as Q35B; continuing on 0+1"; fi
fi
wait $PB
[ "$(rows Q35B)" -lt 792 ] && [ "$(date +%s)" -lt "$DEADLINE" ] && { log "Q35B: $(rows Q35B) rows, retrying the missing"; gq Q35B "$SHA_B" "$(basename "$GB")"; }
log "Q35B GPQA done: $(rows Q35B) rows"

# 5. analysis
{ echo "== M1: DSV9 vs Q35B"; "$PY" "$QA/../ds41-h2h/analyze_ds41.py" DSV9 Q35B --json "$SD/RESULT_m1.json"
  echo "== GPQA: Q35B -> DSV9"; "$PY" "$SD/analyze_gpqa.py" "$RAW/gpqa_Q35B.jsonl" "$RAW/gpqa_DSV9.jsonl" --json "$SD/RESULT_gpqa.json"; } >> "$LOG" 2>&1
log "analysis rc=$?"
finish 0
