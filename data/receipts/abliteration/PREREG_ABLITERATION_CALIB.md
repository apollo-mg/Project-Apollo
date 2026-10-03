# Pre-registration: does abliteration cost calibration (abstention, fabrication) and knowledge, and does OrcaSAQ2's "proprietary" recipe beat plain IQ4_XS at the same size? (Qwen3.8-27B, OrcaRouter Uncensored)

**Registered 2026-10-03, before any row.** Mark: "that's an underserviced yet increasingly popular subset of models
... Happy to run some tests on it."

**The model:** `orcarouter/OrcaSAQ-2-Cyber-27B-Uncensored-GGUF` @ `a0ebe1b5`, `OrcaSAQ-2-27B-Uncensored.gguf`.
- **Hash:** sha256 `4ab6bdf8a9008869abf1630fb92d04b5439805f96b56692962fa240b1d439977`, verified at fetch against HF.
- **Size and recipe:** 15,676,553,472 bytes; IQ4_XS 439 / Q5_K 65 / Q6_K 2 tensors, F32 norms.
- **Base:** `orcarouter/Qwen3.8-27B-Uncensored`, abliterated.
- **The card's claims:** KLD 0.020, top-1 94.4 %, +0.80 % PPL vs BF16, from a "proprietary sensitivity-aware
  mixed-precision" system.
- **The org's own comment:** "equivalent to ~3 bit already in terms of footprint". That does not fit: 15.68 GB is
  ~4.5 bpw, larger than their own plain IQ4_XS (15.31 GB). Their IQ3_XXS is 11.64 GB.

**Prior art checked:** `ledger_precheck.py "abliteration calibration abstention fabrication quant recipe matched
size"` -> receipts found:
- **quant-abstention (INDEX L156):** quantisation degrades knowledge before calibration, and calibration improves as
  it goes.
- **L526:** Qwen3.8-27B Q8_0 on M1, hard accuracy 0.50 (stored rows).
- **L294:** M1 discordance <= 12.5 %, so 240 items per arm is under-powered for small differences.
- **L302:** AgentWorld never refuses, so abliteration was unnecessary there.
- **What this adds:** nothing in the ledger measures abliteration's effect on abstention or fabrication. A
  "proprietary" quant recipe is tested at matched size against plain IQ4_XS of the same weights.

## Arms

| arm | weights | file | bytes |
|---|---|---|---:|
| **S6** | stock Qwen3.8-27B | the .73 daily `Qwen3.8-27B-Q6_K.gguf` (22,884,408,288 B; Q6_K 361 / Q8_0 49) | 22.88 GB |
| **U6** | abliterated (OrcaRouter) | `orcarouter/Qwen3.8-27B-Uncensored-GGUF` @ `fc437a33` Q6_K | 22.43 GB |
| **U4s** | abliterated | OrcaSAQ-2 (above) | 15.68 GB |
| **U4x** | abliterated | same repo @ `fc437a33`, plain IQ4_XS | 15.31 GB |

- **Hashes:** U6 and U4x sha256 are recorded at fetch against the HF LFS hashes (`1a0d6fe2…`, `c52df3e4…`).
- **Recipe check before rows:** S6's and U6's tensor recipes are compared. If they differ beyond Q6_K/Q8_0
  placement, the S6-U6 contrast is reported as weights plus recipe.

## Instrument

- **Server, the same for every arm:**
  - one binary (stated in the run-plan addendum), `-ngl 99 -sm layer -fit off -fa on -c 8192 -np 1
    --no-cache-prompt --jinja -ctk f16 -ctv f16 -lv 4`;
  - no MTP or speculative decoding;
  - `--chat-template-kwargs '{"reasoning_effort":"medium","enable_thinking":false}'`.
- **Gates per arm:**
  - `/props` model path;
  - all layers on GPU;
  - no `VBR dynamic` line (f16 KV);
  - G2 thinking off (empty reasoning, non-empty content);
  - `/tokenize " UNKNOWN"` gives the variant ids M1 expects.
- **Batteries:**
  - **IKP:** `data/receipts/ikp/ikp_run.py --tiers T1,T2,T3,T4 --max-tokens 64 --no-think --exclude-source
    researcher`, 714 probes (`ikp_probes.json` sha256 `fe8c84af…`), scored by `ikp_score.grade()`. committed =
    C/(C+W), fabrication = W/(C+W), plus refusal rate.
  - **M1:** `quant-abstention/run_main.py`, 240 items (easy / hard / invented), temp 0. Reported: easy accuracy,
    hard correct, hard answered-wrong, invented refused.
  - **KLD:** `llama-perplexity` against U6's logits, wikitext-2 test, 16 x 512, f16 KV. S6, U4s and U4x are each
    scored against U6. U6 is a Q6_K stand-in for the BF16 the card compares against, so card numbers are context,
    not equivalents.
- **Order:** U6, S6, U4s, U4x, then KLD. Exact McNemar per item for the paired IKP and M1 contrasts.

## Predictions (`analyze_abliteration.py`, self-tested before rows)

| # | claim | rule | confidence |
|---|---|---|---|
| A1 | **abliteration lowers abstention on invented items** | M1 invented-refused U6 <= S6 - 0.15 | 0.5 |
| A2 | **abliteration raises fabrication** | IKP fabrication U6 >= S6 + 5 pp | 0.45 |
| A3 | **abliteration keeps knowledge** | IKP raw accuracy U6 within 3 pp of S6 | 0.6 |
| A4 | **abliteration barely moves ordinary text** | mean KLD(S6 vs U6) < 0.05 | 0.5 |
| R1 | **SAQ2 beats plain IQ4_XS at matched size** | KLD(U4s) <= 0.8 x KLD(U4x), both against U6 | 0.5 |
| R2 | **the card's fidelity roughly holds** | KLD(U4s vs U6) <= 0.030 (card 0.020 vs BF16, plus Q6_K's own floor) | 0.55 |
| R3 | **SAQ2 keeps the calibration it started with** | M1 invented-refused U4s within 0.10 of U6, and IKP raw within 3 pp | 0.6 |

**Reported without a prediction:**
- S6 against the stored Q8_0 M1 rows (L526) as an anchor;
- per-tier IKP;
- top-1 agreement;
- U4x on the same batteries.

## Not tested

- **Cybersecurity skill and harmful-request behaviour.** "Cyber" appears to be branding for a separate closed-beta
  model; this measures calibration and knowledge only.
- **Thinking on.**
- **The BF16 originals.**

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
- **Run-plan addendum (before any row; 10-03 ~12:00). Not a deviation:** it fills in what the prereg left to be
  stated.
  - **Host:** .194 split into two independent 2-GPU halves.
    - **A:** GPUs 0,1 + `numactl --cpunodebind=0 --preferred=0`, port 8191.
    - **B:** GPUs 2,3 + socket 1, port 8192.
    - Same P100 model and deterministic kernels, so the half affects speed, not outputs.
    - .194 is at 150 W / 1063 MHz.
  - **Binary:** buun `0b2789f23` (`~/buun-0b278/build_sm60`, `llama-server` and `llama-perplexity`) for every arm.
  - **Waves (63 GB free on .194):**
    - wave 1 = U6 (A) and S6 (B) in parallel, then U6's KLD reference logits and S6's KLD (A);
    - then both files are deleted;
    - wave 2 = U4s (A) and U4x (B), then their KLDs in parallel.
  - **Hashes:**
    - S6 `562fbf760503008f118e5df38de5b3e97992d1f693f475815631198547486727`, from .73's daily file;
    - U6 `1a0d6fe2…a24d7` and U4x `c52df3e4…45e0af`, matching HF LFS;
    - U4s `4ab6bdf8…439977`, matching HF.
    - Each is re-hashed on .194 after copying.
  - **Recipe check (done):** S6 and U6 have the same 866 tensor names, but 145 differ in type.
    - S6, the daily file, keeps `ssm_alpha` / `ssm_beta` (5120x48) in F32 and 49 `ssm_out` in Q8_0;
    - U6 has all of these in Q6_K.
    - **So S6 vs U6 is reported as weights plus recipe** (as anticipated above). A1-A4 keep their rules, but their
      wording becomes "the OrcaRouter abliterated Q6_K" vs "the stock daily Q6_K".
  - **Per-arm gates add:** `/tokenize` of " UNKNOWN" / " Unknown" / " unknown" must return [59322] [21024] [9496]
    (M1's variant ids); a mismatch stops the arm.
  - **Runner** `run_abl.sh`. Analysis `analyze_abliteration.py`, self-test passed.

