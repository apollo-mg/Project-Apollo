# Pre-registration -- Sage-A1.5 vs its base at matched precision: is Sage's -0.22 on invented items a tuning effect or a Q8_0-vs-Q6_K artifact?

**Registered 2026-11-08, before any row.** Mark approved the download on 11-08 ("Yep good to grab it. Curious if the results
change."). Only procedure has run: the download (size and sha256 against the HF API's LFS oid).

**Why.** `RESULT_SAGE.md` paired Sage-A1.5 at **Q8_0** (InternScience's official GGUF) with its base Qwen3.6-35B-A3B at a
plain **Q6_K** (mradermacher static) and found Sage refusing invented questions 0.22 less often (0.45 vs 0.67). An
independent replication of our Arete result (Jorge Leon, HF discussion #23 on NousResearch/Arete-27B; 4-bit MLX, his own
30 invented questions, greedy, thinking off) confirmed Arete's direction but found Sage holding its base's rate (15-17/30
vs 15/30). Our precision mismatch is the obvious candidate. This run removes it.

**Prior art checked:** `ledger_precheck.py "Sage Qwen3.6-35B-A3B precision quant mismatch abstention"` -> INDEX L572/L574
(the Sage result itself) and the 27B quant bound quoted in `RESULT_SAGE.md`: on the 27B, the nearest ~4-bit files moved
U refusal by about 0.02 from Q8_0 (UD IQ4_XS), and a 3.5 bpw file by 0.06 (upward). Q6_K sits above both. **What this
adds:** the same comparison with both models in the same packager's same quant, the same build and the same day, plus a
replay of the stored base arm as control. It answers whether the -0.22 survives matching; it cannot say why Leon's set
disagrees if it does.

## Files

| arm | file | source |
|---|---|---|
| SGQ6 | `Sage-A1.5.Q6_K.gguf`, 29,208,732,672 B, sha256 `852dffdd...` | mradermacher/Sage-A1.5-GGUF @ `fedd56b6` (static, no imatrix) |
| Q36B2 | `Qwen3.6-35B-A3B-Q6_K.gguf`, 28,514,152,928 B, sha256 `0e0e2c37...` -- the file the stored Q36B arm ran | mradermacher static, NAS `from_73_20260827` |

- **Recipe check (recorded, not a gate):** the per-tensor type map of SGQ6 against the base file (`arete/tensor_map.py`).
  The 694 MB size difference and any tensor whose type differs are reported with the result.
- **Hashes** are checked on .194 before the servers start; a mismatch stops the run.

## Instrument: a procedural copy of `sage_chain.sh`, which produced the stored SGOFF and Q36B arms

.194, all four P100s, upstream llama.cpp `c7fc509` build_sm60 started by the same `~/bench/sage/serve_sage.sh` (`-ngl 99
-sm layer -c 16384 -ctk f16 -ctv f16 -np 1 -fit off`, `GGML_CUDA_ALLREDUCE=internal`, port 8190); weights from
`/dev/shm`, one file at a time; `run_main.py` M1, thinking off, greedy, 1,024 tokens, 600 s timeout, R-slot on,
`--usage`, no system message, no template kwargs. The arms run in turn: **Q36B2 first, then SGQ6.** No change from the
stored arms except the Sage file and the day.

## Gates (before any row of the arm; each failure stops the run)

1. Each file's sha256 verified in `/dev/shm` on .194.
2. The server serves that file (`/props` `model_path`), and its recorded PID's command line carries `-ctk f16 -ctv f16`
   (this build does not log the KV line at default verbosity).
3. **Prompt gate:** `ds41-h2h/prompt_gate.py` (240 rendered and tokenized M1 prompts, one hash) runs on the Q36B2 server
   and again on the SGQ6 server; SGQ6's hash must equal Q36B2's before any SGQ6 row. `run_main.py` also enforces the
   stored Q36B arm's render tail and UNKNOWN token ids on both.
   *Contingency, registered now:* if the hashes differ, the two templates render M1 differently, so the stored
   comparison carried that difference too. SGQ6 then runs as the stored arm did, and a third arm **SGQ6T** (the same
   file served with the base GGUF's chat template via `serve_sage.sh`'s template argument) runs after it; it must pass
   the gate against Q36B2, and SGQ6T vs Q36B2 becomes the primary comparison.
4. Smoke per arm (as `sage_chain.sh`): a short request returns non-empty content and empty reasoning.

## Analysis (`ds41-h2h/analyze_ds41.py`, committed and generic over arms)

Primary: SGQ6 vs Q36B2 paired by item (E, H, H abstained, U refused strict and lenient, U confabulated, unfinished;
bootstrap 10,000, seed 20261103; exact McNemar). Control: Q36B2 vs stored Q36B with `--replay` (byte identity of
`content`). Secondary: SGQ6 vs stored SGOFF (precision and packager together, within Sage). Descriptive: mean R-slot
P(UNKNOWN) on U.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **The -0.22 is a tuning effect, not a precision artifact** | U refused SGQ6 - Q36B2 <= -0.10, CI upper < 0 | 0.75 |
| P2 | **Precision moves Sage little** | \|U refused SGQ6 - SGOFF\| <= 0.05 | 0.65 |
| P3 | **The base replay reproduces the stored Q36B arm** | `content` byte-identical on >= 238 of 240 | 0.9 |

**What each outcome does to the receipts** (U refused SGQ6 - Q36B2):
- **point <= -0.10 and CI excludes 0:** the -0.22 is confirmed at matched precision; the matched value is reported beside it.
- **CI excludes 0, point above -0.10:** the drop is real but the mismatch inflated it. The matched value replaces -0.22 in
  `RESULT_SAGE.md` and in the Sage row of `arete/RESULT_ARETE.md`; the fine-tune pattern stays at five of five.
- **CI includes 0:** `RESULT_SAGE.md`'s finding 3 and the Sage row are withdrawn, not caveated; the pattern stands at four
  of five, and Sage joins Granite's IDK adapter as a fine-tune that did not cost abstention.

If P3 fails, the primary comparison still holds (same day, same instrument), and the drift is reported as a finding
about the instrument.

## Addendum 1 -- header checks (2026-11-08, after the download, before any row)

- **Recipe matched** (`raw/logs/sage_q6_tensor_map.txt`): every tensor the two files share has the same type (432 Q6_K,
  301 F32). SGQ6 has 20 more, all `blk.40.*` (`block_count` 41, `nextn_predict_layers` 1): Sage's MTP head, which the
  base conversion lacks (`block_count` 40). That is the 694 MB. The c7fc509 build does not run it: loading the stored
  Sage Q8_0, which carries the same head, it logged "model has unused tensor blk.40... -- ignoring". The stored
  comparison had the same asymmetry, so it is not a new difference.
- **Tokenizer identical:** tokens, merges, token types, pre-tokenizer, BOS/EOS/pad ids. SGQ6 also carries
  `add_eos_token` false and `normalizer.nfc` true, which the base file lacks; the token-level prompt gate catches any
  effect.
- **Templates differ as text** (9,025 vs 7,764 characters; Sage adds the verification switch) but render all 240 M1
  prompts identically under jinja2 (thinking off, no system message). The live gate on the servers' own renderer and
  tokenizer still decides, so the SGQ6T contingency stays registered.
- Chain: `run_sage_matched.sh`; the base template for the contingency is `raw/logs/q36b_chat_template.jinja`, extracted
  from the base GGUF.

## Deviations

Any change to a file, flag, lane or the analysis after the first SGQ6 or Q36B2 row gets a numbered Deviation here.
