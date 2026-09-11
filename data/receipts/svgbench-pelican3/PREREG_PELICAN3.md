# Pre-registration — pelican three-way: base Qwen3.8-27B vs Qwopus3.8-27B-Flash vs DavidAU Twin-Turbo, matched IQ3_M

**Logged 2026-09-11, before BASE or QWOPUS had generated anything.** DAVIDAU's three earlier reps
exist (`svgbench-davidau/RESULT_TOKENS.md`). They are reported separately, not pooled.

## The question

Two fine-tunes of Qwen3.8-27B each claim to cut reasoning:

- **DavidAU's Twin-Turbo** claims "1/5 to 1/2 the thinking tokens".
- **Jackrong's Qwopus3.8-27B-Flash** (SFT, then NeMo-RL GSPO) has a card that reports:
  - P95 output length down 13–40%;
  - median output length *up* in all three reported subjects;
  - MMLU-Pro 91.28 against the base's 92.73.

On the pelican prompt, at matched quantization, how do tokens, thinking and the drawings compare
against the base?

## Arms

| arm | file | source (repo @ commit) | bytes | sha256 |
|---|---|---|---|---|
| BASE | `Qwen3.8-27B.i1-IQ3_M.gguf` | `mradermacher/Qwen3.8-27B-i1-GGUF` @ `9eb2d6db` | 12,768,331,744 | `7544860b…0f3cd40` |
| QWOPUS | `Qwopus3.8-27B-Flash.i1-IQ3_M.gguf` | `mradermacher/Qwopus3.8-27B-Flash-i1-GGUF` @ `a2f33e11` | 12,768,328,256 | `f31b7ae2…6313c08c` |
| DAVIDAU | `…-NM-DAU-NEO-MTP-IQ3_M.gguf` | `DavidAU/Qwen3.8-27B-TWIN-TURBO-…-NEO-MTP-GGUF` @ `7ee443a7` | 12,819,866,976 | `d25b96e4…7817ef8dd6` |

Full hashes are in `/mnt/TG_2TB/AI/Models/pelican3/manifest.txt`. Files are verified against the
Hugging Face LFS hash before use.

**Quantization, read from the GGUF headers:**
- **BASE and QWOPUS use an identical recipe:** 0 of 866 tensor types differ; same imatrix dataset
  (`imatrix-training-full-3`, 319 chunks).
- **DAVIDAU is close but not identical:** 6 tensors differ in type (IQ3_S 409 / Q4_K 96, against
  415 / 90), and it uses DavidAU's own NEO imatrix.
- **All three carry the MTP head.** No arm uses speculation.

## Templates

Each arm runs its own shipped template, as users get it.

- **BASE and DAVIDAU** render the pelican request byte-identically at `medium`:
  `<|im_start|>user\n…<|im_end|>\n<|im_start|>assistant\n<think>\n`. Neither injects effort text at
  `medium`.
- **QWOPUS's template has no `reasoning_effort` handling.** It renders the same prompt without the
  trailing `<think>\n`, leaving the model to open thinking itself.
- **This difference is measured, not controlled.** Rule R2 checks every QWOPUS rep for whether it
  opened thinking.
- **The rendered prompt is logged every rep,** from the server's own `/apply-template`.

## Held identical to `PREREG_TOKENS.md`

- **Harness:** `run_ladder.py` functions via `tools/svgbench/run_one_p1.py`, driven by
  `pelican3_rep.sh`.
- **Prompt:** *"Generate an SVG of a pelican riding a bicycle."*
- **Server flags:** `-c 24576 -n 20000 -np 1 -fa on --kv-unified -ctk q8_0 -ctv q8_0
  --reasoning-effort medium --min-p 0 --jinja`.
- **Sampling:** temperature 1.0.
- **Binary:** `engines/buun-llama-cpp/build_rocm` (`3823c9eb6`).
- **Card:** RX 9070 XT at 330 W.
- **Scorer:** `svg_probe.py`, unchanged.
- **Memory safeguards:** preflight, watchdog and cooldown.
- **Procedure:** first drawing only, fresh server per rep.

**One declared deviation: generation is capped at 480 s.** At the 27.5 t/s measured for IQ3_M, that
is about 13k tokens. The cap keeps each rep inside a 10-minute foreground job; heavy background jobs
have been killed by the tool harness on low memory. All 13 earlier first drawings would have finished
under it (max 10,503 tokens in 362 s).

## Design

5 reps per arm, fresh, in rotated order:

| rep | order |
|---|---|
| 1 | QWOPUS, BASE, DAVIDAU |
| 2 | BASE, DAVIDAU, QWOPUS |
| 3 | DAVIDAU, QWOPUS, BASE |
| 4 | QWOPUS, BASE, DAVIDAU |
| 5 | BASE, DAVIDAU, QWOPUS |

QWOPUS goes first, so R2's check happens on the very first generation.

**Recorded per drawing:**
- completion tokens
- reasoning chars
- answer chars
- structural score
- SVG and render
- elapsed time
- rendered-prompt hash and `kv_bpv`

## Rules, fixed before any generation

- **R1 — capped rep.**
  - **Definition:** a rep whose generation hits the 480 s cap, or the 585 s wall-clock backstop once
    generation has started, is a runaway. It is recorded, not rerun.
  - **Token comparisons:** it ranks above every completed rep; capped reps tie with each other.
  - **Excluded from** thinking-length and score comparisons.
- **R2 — did the rep think?** A rep opened thinking if `reasoning_content` is non-empty, or if
  `content` contains `</think>`.
  - **Parser miss:** if `reasoning_content` is empty but `content` contains `</think>`:
    - thinking chars = the text before the last `</think>`, minus a leading `<think>`;
    - the scored SVG is the last `<svg…</svg>` *after* `</think>`, re-probed with `svg_probe.py`.
  - **No thinking at all:** a QWOPUS rep that never opens thinking is reported separately. It is
    excluded from thinking-length comparisons and kept in token comparisons.
- **R3 — no generation, or a killed one.**
  - A rep whose server never became ready is rerun, since nothing was generated.
  - A rep the memory watchdog killed mid-generation is rerun once and logged as an incident.
- **R4 — prompt integrity.** A rep whose rendered prompt differs from its arm's other reps is
  invalid and rerun.
- **R5 — KV integrity.** `kv_bpv` should read 8.5 for q8_0 in every rep. A rep that differs from the
  others is invalid and rerun (AFM-38).

## Predictions

| id | prediction | conf |
|---|---|---|
| P-P1 | DAVIDAU thinks less than BASE: fewer reasoning chars. Exact one-sided Mann-Whitney, 5 v 5, α = 0.05 | 80% |
| P-P2 | DAVIDAU uses fewer completion tokens than BASE (same test) | 45% |
| P-P3 | QWOPUS median completion tokens ≥ BASE median: the card's median claim, on a new task | 55% |
| P-P4 | QWOPUS opens thinking in all 5 reps | 85% |
| P-P5 | No rep hits the cap (R1) | 85% |
| P-P6 | All 15 drawings are structurally sound: 10/10, or failing only on the artifact types in `svgbench-ladder/RUN_NOTES.md` | 50% |

- **P-P1:** in the earlier test DAVIDAU thought 0.22× as much as the historical stock arm
  (p = 0.014, 3 v 10). This is the first test against a matched base.
- **P-P2:** the earlier ratio was 0.69× (p = 0.108), because DAVIDAU's answers ran 1.41× longer.

## Power

- **5 v 5:** the exact one-sided Mann-Whitney test reaches at best p = 1/252 ≈ 0.004. Only large
  effects clear α = 0.05.
- **Tails:** the card's P95 claim is not testable with 5 draws per arm. Maxima will be reported, not
  tested.

## What will not be claimed

- Nothing about other prompts, other effort modes or benchmarks.
- **No taste ranking.** The structural score is mechanical, and the drawings go to Mark unblinded.
  Any preference he states is informal; a blind panel would need its own prereg.
- **No comparison with the ladder's 10 stock drawings.** They are unsloth UD at 2 and 4 bits, a
  different packager and quant level.
- Nothing about MTP; the heads are present but unused.
- Nothing about "intelligence".
