# Overnight 2026-09-09 → 09-10: what is running and how to read it

Launched 00:32. Two arms, unattended, each capped at 2.5 h (`timeout 9000`). Worst case ~5 h.
Full design and predictions: `../PREREG_CACHE_REUSE_AB.md` (logged before the run).

## To see the answer

```bash
cd /mnt/TG_2TB/Projects/Apollo/data/receipts/viability/cache-ab
tail -20 pd2_driver.log                      # arm transitions
for t in pd2_novbrcache pd2_control; do
  echo "== $t"; python3 - "$t" <<'PY'
import json,glob,os,sys,collections
t=sys.argv[1]; rd=f"/home/mark/projects/hermes-bench-tool-call/results/{t}"
c=collections.Counter(json.load(open(f)).get('status')
    for f in glob.glob(rd+'/*.json') if os.path.basename(f)!='summary.json')
print('  ', dict(c))
w=f"wire_{t}.jsonl"
if os.path.exists(w):
    tx=[json.loads(l) for l in open(w)]
    tx=[d for d in tx if d.get('ev') in ('response','aborted') and (d.get('text') or '')]
    deg=[d for d in tx if d['text'].count('/')/max(1,len(d['text']))>0.9]
    print(f'   responses {len(tx)}, >90% slashes {len(deg)}')
PY
done
```

**The wall clock alone tells you the answer.** A clean 20-task run is ~11 min. A latched one is
~90 min. If an arm took over an hour, it latched.

## How to interpret (pre-committed, do not renegotiate)

| Arm A `pd2_novbrcache` | Arm B `pd2_control` | conclusion |
|---|---|---|
| clean | latches | **idle-slot VBR capture is the mechanism** — the good outcome |
| latches | latches | not idle capture; backpressure corrupts by some other path |
| clean | clean | the proxy edit changed inline behaviour; **both arms void**, re-test |
| latches | clean | incoherent; suspect drift, re-run everything |

Arm B is the positive control. It exists because `llm_proxy.py` was edited *after* the three inline
latches, so a clean Arm A on its own cannot distinguish "the flag worked" from "my edit broke the
repro". Do not read Arm A without Arm B.

Predictions: **P-D2 50%** (Arm A clean), **P-D3 85%** (Arm B latches).

## State of the investigation

**Established:** a slow SSE consumer makes llama-server (VBR floor t2, IQ3_XXS, gfx1201) latch into
degenerate `/` output until restart. Isolated single-variable: inline drain 3/3 latched,
decoupled drain 0/1, direct client 1/2. See `../RESULT_SLASH_DEGENERACY.md`.

**Tonight's question:** *which* code path corrupts. Hypothesis is idle-slot VBR re-tiering —
a slot stalled mid-generation classified idle and its KV re-quantised in place.

**Unexplained:** v5 latched at task 16 with a direct client and no proxy.

**Usable number:** IQ3_XXS on tasks 1-20 is **18-19/20** on clean runs.
`t03_patch_edit/t05_v4a` fails in every clean run — genuine content failure.

## Not yet sent anywhere

Nothing about the backpressure finding has gone to buun or Tom. It needs Mark's approval and his
words. The RDNA4 narrow-matmul comment on turboquant#363 *did* go out (approved, 2026-09-09).
