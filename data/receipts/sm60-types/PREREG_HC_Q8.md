# Pre-registration: does converting GSQ-RCO's 192 BF16 hyper-connection matrices to Q8_0 close its decode gap?

**Registered 2026-09-29, during `PREREG_SM60_TYPES.md`'s run and before any row of this one.** The follow-up that
prereg named: "If T3 and T4 hold, the causal test is ... convert GSQ-RCO's 192 hyper-connection tensors from BF16 to
Q8_0, change nothing else, and measure decode." Mark: "I'm laser focused on this paragraph".

**Prior art checked:** this directory, from blocks 0-1 of the kernel run (Deviation 1 discloses what was seen):
- at 1063 MHz, the per-tensor kernel sum puts GSQ-RCO 6.4 ms/token above UD-Q2, with **+6.1 ms from the
  hyper-connections**; the measured decode gap is 6.0 ms;
- BF16 at `hc_up`'s shape (k=320, m=10240) takes 82 us against Q8_0's 23 us, while BF16 at the stock shape matches F16.

`ledger_precheck.py "hyper-connection bf16 q8_0 retype"` -> two tangential rows:
- `battle16gb/FA_EQUIVALENCE_SM60.md` (07-30): whole-model BF16 -> Q8_0 costs less fidelity than `-fa on`. That is
  context for H4, which it does not decide: that was a different model and every tensor, here it is 192 tensors;
- the DavidAU MTP-head row, which is unrelated.

**What this adds:** a causal test, where the kernel run only attributes. One variable, applied to a real file, measured on
real decode. Plus the kernel control the kernel run lacks: F16 and F32 at the same shapes.

## The intervention

- **Tool:** `tools/gguf_retype.py` rewrites **shard 1** of the base (ISTA-DASLab GSQ-RCO IQ3_XXS, sha256 `219ea929…6d15`).
  It converts only tensors matching `hc_(attn|ffn)_(up|down)\.weight` (192, all BF16) to Q8_0, with ggml's reference
  quantizer.
- **Checks:**
  - the KV section and every other tensor are copied byte for byte (`--verify` hashes each copied tensor);
  - the Q8_0 blocks were tested bit-exact against gguf-py's `quants.Q8_0` on a synthetic file.
- **Shard 2** (the 28.8 GB `per_layer_token_embd`, unchanged) is a symlink to the original.
- **Arm name:** HCQ8, in `~/AI/Models/fn_gsq_base_hcq8/`. The runner verifies the **full** `/props` path, since the
  basenames match.

## Instrument

- **Host and server:** .194 at the fleet config (150 W / 1063 MHz, read back); buun `0b2789f23`; the kernel run's
  server flags (`-ngl 99 -sm layer -ts 1,1,1,0.6 -c 16384`, f16 KV, `-np 1`). Each server is fresh and verified:
  own log loaded, full path, 49/49 on GPU.
- **Order:** HCQ8, then GSQB again (a bracket against the kernel run's GSQB decode, taken ~30 min earlier).
- **Per server:**
  - G0 coherence (count to 20);
  - one warm-up;
  - the 6 speed prompts x 2 (`swift_fn_probe.py`) = 12 decode rows;
  - greedy agreement: the 12 outputs of each arm compared (first differing character, and identical or not).
- **Fidelity:** `llama-perplexity --kl-divergence` of HCQ8 against GSQB logits, on wikitext-2 test, 16 chunks of
  512, same flags. It is built after the kernel run finishes, so no build runs during a registered measurement.
- **Kernel control:** `test-backend-ops perf` on GPU 0 at E, 3 repetitions, with cases F16, F32, BF16 and Q8_0 at
  (k=320, m=10240) and (k=10240, m=320). This is a second patched copy, `fn_hc_cases.inc`.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| H1 | **The conversion speeds GSQ-RCO up** | HCQ8 median decode >= 1.07x GSQB (bracketing run) | 0.6 |
| H2 | **...to UD-Q2's speed** | HCQ8 within +/-3 % of UD-Q2's decode at E in the kernel run | 0.4 |
| H3 | **It is the short-row float path, not BF16** | F16 at (k=320, m=10240) >= 2x Q8_0's time there | 0.6 |
| H4 | **The conversion is nearly free in fidelity** | mean KLD(HCQ8 vs GSQB) < 0.01 | 0.7 |

**Reported without a prediction:** F32 at both shapes, the greedy agreement, top-1 agreement from the KLD run, and file
sizes.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.

### Deviation 2 (2026-09-29 ~20:20, AFTER all registered rows): a GSQB-vs-itself KLD control

- H4 failed (0.0153). To know whether any of that is run-to-run noise, `llama-perplexity` scored GSQB against its own
  saved logits, same flags (`raw_hc/kld_self_control.txt`): mean KLD 0.000000, same top 100 %.
- Post-hoc and labelled as such. It does not change any verdict.
