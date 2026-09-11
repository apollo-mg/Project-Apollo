# Pre-registration — does DavidAU's Twin-Turbo tune think less than stock Qwen3.8-27B on the pelican?

**Logged 2026-09-11, before the model had generated anything.**

## The claim under test

The model card says: "1/5 (as low as 1/20 in some cases) to 1/2 the thinking tokens (vs reg Qwen
3.8) across all 5 modes of operation". The card gives no method.

The two templates make a fair comparison possible at `reasoning_effort` **medium**. Both DavidAU's
template and stock's insert **nothing** at medium. Their other modes insert text; DavidAU's
"einstein" mode asks for "at least 5000 tokens" of thinking. So at medium, any difference comes from
the weights, not the prompt.

## Arms

- **DAVIDAU:** `Qwen3.8-27B-TTURBO-Fable-C-Fusion-709-L-Uncen-NM-DAU-NEO-MTP-IQ3_M.gguf`.
  - 12,819,866,976 bytes, sha256 `d25b96e4…`, verified against Hugging Face (repo commit `7ee443a7`).
  - It carries an MTP head, which is not used.
- **STOCK (historical):** the ten ladder first drawings from 2026-09-10, `svgbench-ladder/results.jsonl`.
  - Completion tokens, sorted: 2639, 2699, 2940, 3646, 4397, 4543, 4996, 5160, 6249, 10503.
  - Median **4,470**.

## Held identical to the ladder

- **Harness:** `run_ladder.py`, used through a wrapper that changes only the model and the output
  directory.
- **Prompt:** *"Generate an SVG of a pelican riding a bicycle."*
- **Server:** `-c 24576 -n 20000 -np 1 -fa on --kv-unified -ctk q8_0 -ctv q8_0 --reasoning-effort medium
  --min-p 0 --jinja`, at temperature 1.0.
- **Binary:** `engines/buun-llama-cpp/build_rocm` (`3823c9eb6`).
- **Card:** RX 9070 XT at 330 W.
- **Scorer:** `svg_probe.py`, unchanged since the ladder ran.
- **Memory safeguards:** preflight, watchdog and cooldown, reused from the ladder runner.

**Declared differences, not controlled:**
- **Packager:** DavidAU's own "NEO" imatrix vs unsloth UD.
- **Quant level:** IQ3_M, between the ladder's 2-bit and 4-bit arms.
- **Historical control:** the stock arm ran yesterday, not alongside this one.

## Design

3 reps of the first drawing only, with a fresh server per rep, as in the ladder. Recorded per drawing:
- completion tokens
- reasoning characters (whether thinking fired)
- the structural score
- the SVG and its render

## Predictions

| id | prediction | conf |
|---|---|---|
| P-D1 | Median DAVIDAU completion tokens are **at most 2,235**, half the stock median: the weaker end of the card's claim | 35% |
| P-D2 | DAVIDAU uses fewer tokens than STOCK. Exact one-sided Mann-Whitney, 3 vs 10, α = 0.05 | 60% |
| P-D3 | All 3 DAVIDAU first drawings are structurally sound: 10/10, or failing only on the artifact types in `svgbench-ladder/RUN_NOTES.md` | 65% |

## Power

With 3 draws against stock's wide spread (2,639–10,503), only a large effect is visible. If all three
DAVIDAU drawings come in below all ten stock drawings, p = 1/286 ≈ 0.003. If they sit among the stock
values, this design cannot tell a modest saving from noise, and the report will say so.

## What will not be claimed

- Nothing about the other modes.
- Nothing about benchmarks other than this one.
- Nothing about "intelligence".
- Not a general token saving from 3 drawings of one prompt.
