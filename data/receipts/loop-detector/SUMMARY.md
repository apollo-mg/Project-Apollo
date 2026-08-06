# Loop-detector validation — attempt 1: KAT-Coder never wedges, so it can't test the detector

**Date:** 2026-07-26 · **Node:** `.73` dual Tesla P100, 1063 MHz / 150 W
**Model:** `Kwaipilot_KAT-Coder-V2.5-Dev-Q4_K_M.gguf` · buun_vbr build,
`-c 32768 -np 1 -ngl 999 -fit off -fa on -sm tensor -ts .85,1.15 --reasoning on --jinja`
**Design:** 10 problems × K=2 = 20 generations, temp 0.7 / top_p 0.95 / top_k 20,
**max_tokens 16000**. Problems chosen to contain both classes the detector must separate:
- **HARD** — `HumanEval/32, 91, 132, 145`: the four unsolved by *every* config in the
  HumanEval+ panel, and the source of the longest reasoning in the campaign. Wedge candidates.
- **CONTROL** — `HumanEval/0, 10, 20, 30, 40, 50`: all passed in the 2×2. Healthy terminators.

## Result: the detector could not be tested, because there was nothing to detect

| | n | median gzip ratio |
|---|---|---|
| cap-hitters (`finish=length`) | **0** | — |
| terminators | 15 | **0.494** |

**KAT-Coder-V2.5-Dev did not wedge once in 20 generations** — including on all four
fleet-ceiling problems. Every generation terminated on its own well inside a 16 000-token
budget. (5 of 20 traces were under the 200-byte floor for a meaningful compression ratio and
are excluded from the ratio column; none of them hit the cap either.)

All 15 measurable ratios, sorted:

```
0.3326 0.3410 0.3743 0.4228 0.4357 0.4424 0.4619 0.4938
0.5167 0.5520 0.5780 0.6366 0.6395 0.6862 0.7491
```

Unimodal, range 0.33–0.75. **H2 (bimodality) is untestable on this sample** — there is only
one mode because there is only one behaviour.

## What this is still worth

**1. Healthy reasoning lives at 0.33–0.75; the loop band is 0.08–0.12.** The prior temp-0
Laguna analysis put degeneration loops below 0.08. Nothing in this sample comes within 4× of
that. So *if* loops appear, the separation should be wide rather than marginal — a threshold
detector is plausible. That is a necessary condition, not a demonstration.

**2. KAT terminates where Laguna does not, and that is a real comparison.** On the same four
problems, Laguna-Q2 produced 8 000+ token reasoning and wedged; KAT solved or abandoned them
in ~1 000 tokens. Consistent with KAT's stated brevity design, and consistent with the
stopping-rule framing from `data/receipts/humaneval-plus/`: the deficit there was Laguna
failing to *stop*, and here is a model that stops.

**3. It rules out the cheap path.** The detector has to be validated on a model that actually
exhibits the failure. That means **Laguna on .194**, which is committed to stage 2 for ~20 h.

## Why not just use another .73 model

`Darwin-36B-Opus-ABLITERATED-HERETIC` and `Qwopus3.6-27B-Coder-heretic` are plausible wedgers
(heavily modified checkpoints tend to be less stable). But a detector validated on an
abliterated model says little about whether it would fire correctly on the model we would
actually deploy it for. Better evidence is worth the wait.

## Next attempt — design notes

- Run on **Laguna-S-2.1-Q2** when .194 frees. That model is *known* to produce 11/492
  non-terminating samples, so positives are guaranteed rather than hoped for.
- Include the 2×2's `persona + tools` cell: it produced the campaign's only observed wedge
  under otherwise-normal conditions (`HumanEval/30`, 2 260 → 71 375 chars). A condition that
  reliably induces wedges is worth more than a problem set that might.
- **Measure the false-positive rate, not just recovery.** A threshold that recovers wedges by
  aborting legitimate long reasoning is a net loss. Both rates are needed before this becomes
  a recommendation.
- The current probe scores compression on the *completed* trace. A deployable detector has to
  score a **sliding window mid-stream**; a loop that starts at token 4 000 will not drag the
  whole-trace ratio below threshold until far too late. Whole-trace ratio is the offline
  proxy, not the mechanism.

## Files

| file | what |
|---|---|
| `loop_probe_kat.json` | per-generation finish, tokens, reasoning length, gzip ratio |
| `loop_traces_kat/` | all 20 full traces (reasoning + content), kept regardless of outcome |
| `loop_probe_kat.log` | console output |
| `loop_probe.py` | the probe |
| `run_loop_probe_73.sh` | driver — swaps the Coordinator for KAT and restores it byte-exactly from captured argv |
