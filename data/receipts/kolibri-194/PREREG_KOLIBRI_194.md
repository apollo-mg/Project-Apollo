# Pre-registration: does Aleph Alpha's Kolibri-1 (78B-A3.46B MoE) run correctly and how fast, fully VRAM-resident on 4x P100, through the unofficial llama.cpp port?

**Registered 2026-10-06, before any row.** BACKLOG N21 (Mark: "Sure").

**Prior art checked:** `ledger_precheck.py "Kolibri Aleph Alpha MoE sliding window P100"` -> nothing on Kolibri.
- **Nearest:** Flash-Next / GLM-5.3 MoE speed on .194 (qwen4exp, glm53-flash). **What this adds:** the first
  measurement of this model on Pascal, and a sanity check of an unofficial port that 11.6k downloaders are running.
- **No upstream llama.cpp support:** #29922 is open and no PR exists.

## Instrument

- **Model:** `Hob-forge/Kolibri-1-GGUF` @ `47fb91b2`, `Kolibri-1-Q4_K_M.gguf`, 47,454,113,472 B.
  - sha256 `c2ac1301…6062e` (HF LFS), checked on .194 before any row.
  - Its card: converted from Aleph Alpha's FP8 checkpoint, dequantized to BF16, then quantized.
- **Engine:** upstream llama.cpp `836d571` + `kolibri1-llama.cpp.patch` from the same repo revision (4 commits,
  HEAD `60d1d51cc`). Built for sm_60 with CUDA 12.4 and gcc-13 as host. The patch was read before building: model
  code, converter, vocab and one test only.
- **Server:** `-ngl 99 -sm layer -fa on -fit off -c 8192 -np 1 -ctk f16 -ctv f16 --jinja`, thinking off (`--reasoning
  off` if the template has a toggle, recorded either way).
- **Host:** .194 as in `strata-194/` (same boot); clocks recorded.

## Arms and gates

1. **K_load:** the server loads, all layers on GPU (log), `/props` model path.
2. **K_sane:** three fixed questions, greedy, 128 tokens.
   - 2+2.
   - The capital of Germany, asked in German.
   - Define photosynthesis in one sentence.
   - **Gate:** coherent answers in `content`, and the German question answered in German.
3. **K_ppl:** `llama-perplexity` on wikitext-2 test, 16 x 512, `-b 512`. Recorded as a sanity number, not a quality
   claim (no reference to compare with).
4. **K_speed:** `lmx` remote (`run194.sh`-style) on canonical reasoning-v1 and code-v1.
   - 1 warmup + 3 timed, median, one server start each.
   - Evidence captured by `g4_proxy.py`.

## Predictions

| # | claim | confidence |
|---|---|---|
| K1 | the port loads and K_sane passes (coherent, German answered in German) | 0.75 |
| K2 | wikitext-2 PPL is below 15 (the port is not badly broken) | 0.7 |
| K3 | decode on reasoning-v1 is at least 30 tok/s (3.46B active, fully resident) | 0.5 |

## Not tested

- Agreement with the second unofficial port (Eliasfpv28's patch). This is the planned follow-up, since there is no
  runnable reference here.
- Quality against Aleph Alpha's reference.
- Long contexts.
- Reasoning mode.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
- **Addendum K4 (before its rows; 10-06 ~12:45): agreement between the two unofficial ports.** Mark: "Let's check the
  second Kolibri port and see if it's different."
  - **Port 2:** `Eliasfpv28/Kolibri-1-Q3_K_S-GGUF` @ `04f6e403`, `runtime-source/kolibri1-runtime.patch` on upstream
    llama.cpp `edd6e2b`. Read before building: model code, `gguf-py`, converter only. It cites Aleph Alpha's
    inference reference. Built for sm_60 / CUDA 12.4 / gcc-13 like port 1.
  - **The test:** both ports on the SAME GGUF.
    - First choice: Hob-forge's Q4_K_M, if port 2 loads it.
    - Otherwise: port 2's own Q3_K_S in both, if port 1 loads it.
    - If neither cross-loads, the ports are reported as not comparable on one file, with the reason.
  - **Measures:**
    - `llama-perplexity` wikitext-2, 16 x 512, `-b 512`. Port 1's logits are the base; port 2 runs with
      `--kl-divergence` against them.
    - The three K_sane prompts, greedy, compared as text.
  - **K4 prediction:** the ports agree, mean KLD < 0.01 and same top-1 >= 98 % (confidence 0.45). If they do not,
    whichever has the lower PPL on the same file is the better candidate, but neither is proven correct without a
    reference.
  - **K4b (added before any K4 row):** the same base/KLD comparison at `-c 2048 -b 2048`, 8 chunks. At 512 nothing
    reaches past the 513-token sliding window, so a window-semantics difference between the ports could only show at
    the longer context.
- **Deviation K4-1 (after port 1's K4 rows, before any port 2 row; 10-06 ~12:58).**
  - **The failure:** port 2 cannot load Hob-forge's GGUF: "unknown pre-tokenizer type: 'kolibri1'".
  - **Source check:** port 1's patch adds `kolibri1` to the branch that sets `LLAMA_VOCAB_PRE_TYPE_QWEN2,
    clean_spaces = false`, which is identical to `qwen2` in port 2's tree. Port 2's converter also states "Same
    pre-tokenizer regex as Qwen2".
  - **So:** port 2 runs on the same file with `--override-kv tokenizer.ggml.pre=str:qwen2`, which gives identical
    tokenization. This replaces the registered fallback (downloading port 2's own Q3_K_S), so the comparison stays
    on one file.
  - Any other metadata incompatibility is recorded as found.
- **Addendum K5 (before any K5 row; 10-06 ~14:40): does Hob-forge's conversion agree with an independent one?**
  Mark: "We can go ahead and knock out the remaining two".
  - **Prior art checked:** `ledger_precheck.py "Kolibri converter Q3_K_S KLD"` -> only this campaign's K1-K4. **What
    K5 adds:** K4 showed the two ports run one file identically; it could not test the file itself.
  - **The second file:** `Eliasfpv28/Kolibri-1-Q3_K_S-GGUF` @ `04f6e403`, `Kolibri-1-Q3_K_S.gguf`,
    33,870,242,400 B, sha256 `26ce4a2f…d34aa` (HF LFS), checked on .194 before any row. Its `provenance.json`: from
    the official `Aleph-Alpha/Kolibri-1-BF16` @ `7a8f290e`, converted by its own `stream-convert.py`, then
    `llama-quantize --tensor-type ffn_gate_inp=f32 … Q3_K_S`, no imatrix. Hob-forge's card says FP8 checkpoint ->
    BF16 -> Q4_K_M. **So the two files differ in source precision AND in quant, as well as in converter.**
  - **Why PPL/KLD alone cannot decide it:** Q3_K_S-vs-Q4_K_M noise would hide a subtle converter error. So the
    direct comparisons below are the gates, and KLD is the end-to-end figure.
  - **Gates (gguf-py from port 2's tree `edd6e2b`, reading headers and single tensors; no model load):**
    - **K5a, metadata:** every GGUF KV pair compared, except `general.*`, `tokenizer.ggml.pre`, `general.file_type`
      and quantization-version keys. The vocab tokens, token types and merges are compared by hash. **Holds** if every
      other key is equal. Rope base, norm epsilon, sliding window/pattern, expert counts and gating are listed
      explicitly in the result either way.
    - **K5b, tensor list:** the same tensor names and shapes (types may differ). **Holds** if equal.
    - **K5c, tensors stored as F32 in BOTH files** (norms, routers `ffn_gate_inp`, expert biases; which ones qualify is
      read from Hob-forge's header first and listed). Values compared. **Holds** if each is bit-identical, or within
      BF16 rounding (max relative difference <= 2^-7). A +1 norm offset, a sign flip or a permutation fails it.
    - **K5d, quantized weights:** dequantize `blk.0.attn_q.weight` (or the first attention projection present) and
      expert 0 of `blk.0.ffn_gate_exps.weight` and `blk.0.ffn_down_exps.weight` from each file and correlate.
      **Holds** if Pearson r >= 0.95 on each. Q3 against Q4 noise should give ~0.98-0.99. A transpose or permutation
      error gives ~0. r < 0.5 on any is registered as a structural disagreement.
  - **End to end (K5e):** port 2 (`edd6e2b` + its patch, its native file) runs `llama-perplexity` on Q3_K_S with
    `--kl-divergence` against port 1's saved Q4_K_M base logits (`runs_k4/base_p1_c512.bin`, `base_p1_c2048.bin`),
    at 16 x 512 `-b 512` and 8 x 2048 `-b 2048`. PPL and the ratio to Q4_K_M are reported. Port 2 only; K4 already
    showed the ports equal.
  - **Predictions:**
    - K5a-K5c hold (0.65).
    - K5d holds (0.8).
    - K5e: mean KLD < 0.3 and same top-1 >= 80 % at 512 (0.7). KLD > 1.0 or top-1 < 60 % would mean the conversions
      differ materially, with neither proven right. In between is inconclusive.
  - **Not decided by K5:** which conversion is right if they disagree (no reference runs here); quality against Aleph
    Alpha's numbers.
  - **Housekeeping:** the Q3_K_S file is deleted after K5 (re-obtainable at the pinned revision) to make room for
    `strata-194/PREREG_STRATA_194_Q4XL.md`.
