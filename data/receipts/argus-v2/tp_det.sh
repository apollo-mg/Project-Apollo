#!/usr/bin/env bash
# -sm tensor determinism gate. Same prompt, same seed, K repeats, byte-compare.
# HIGH-ENTROPY prompt on purpose: a confident task (primes, arithmetic) produces
# identical output even when logits are perturbed, so it cannot detect reduction-
# order nondeterminism. Open-ended prose at temp 1.0 has a flat next-token
# distribution, where any logit wobble flips a token and then compounds.
# Routed through the wake proxy so requests register as activity.
set -u
K="${1:-15}"; OUT="${2:-/tmp/tp_det.jsonl}"; SEED="${3:-12345}"
: > "$OUT"
P='Write a vivid 200-word description of an abandoned lighthouse at dawn. Be specific and original.'
for i in $(seq 1 "$K"); do
  t0=$(date +%s.%N)
  curl -s -m 300 -H 'Content-Type: application/json' -d "{
    \"model\":\"x\",\"messages\":[{\"role\":\"user\",\"content\":\"$P\"}],
    \"temperature\":1.0,\"top_p\":0.95,\"top_k\":20,\"seed\":$SEED,
    \"max_tokens\":300,\"stream\":false,
    \"chat_template_kwargs\":{\"enable_thinking\":false}}" \
    http://127.0.0.1:8099/v1/chat/completions > "$OUT.raw.$i" 2>/dev/null
  t1=$(date +%s.%N)
  python3 - "$OUT.raw.$i" "$i" "$(echo "$t1 - $t0" | bc)" "$OUT" <<'PY'
import sys,json,hashlib
f,i,secs,out=sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4]
try:
    d=json.load(open(f)); m=d['choices'][0]['message']
    c=m.get('content') or ''
    rec={'i':i,'secs':round(secs,1),'len':len(c),
         'sha':hashlib.sha256(c.encode()).hexdigest()[:16],
         'tok':(d.get('usage') or {}).get('completion_tokens'),
         'fin':d['choices'][0].get('finish_reason')}
except Exception as e:
    rec={'i':i,'secs':round(secs,1),'len':-1,'sha':'ERR','tok':None,'fin':str(e)[:40]}
open(out,'a').write(json.dumps(rec)+'\n')
print(f"[{i}] {rec['sha']} len={rec['len']} tok={rec['tok']} {rec['secs']}s {rec['fin']}")
PY
done
