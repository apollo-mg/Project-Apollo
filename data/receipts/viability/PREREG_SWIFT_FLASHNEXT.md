# Pre-registration: Swift 1.5 on Qwen3.8-Flash-Next, against its base at an identical quant allocation

**Registered 2026-09-29, before any row.** Mark shared `ukisai/Swift-1.5-Qwen3.8-Flash-Next-GGUF` ("Ukis did the Swift
treatment to Flash-Next") and said go. The third Swift model on this fleet, after the 27B and Bonsai 2.

**Prior art checked:** `ledger_precheck.py "Swift Flash-Next"` and `"GSQ-RCO"` -> receipts found:
- `viability/RESULT_SWIFT_BREVITY_TAX.md` (Swift on Qwen3.8-27B): -26 % thinking on false premises; unanswerable
  failures 6/24 vs 4/24 (p = 0.72, a trend);
- `viability/RESULT_SWIFT_BONSAI.md` (Swift-Bonsai-2): near-twins with thinking off (237/240 same grade); 0.73x
  thinking on false premises; the same honesty (17 vs 15/24);
- `quant-abstention/RESULT_FLASHNEXT.md` (Stage A) and `viability/RESULT_FLASHNEXT_STOPPING.md` (Stage B): base
  Flash-Next UD-Q2_K_XL on M1 and on CAL xhigh, on this host and build;
- `qwen4exp/RESULT_FLASHNEXT_MTP_CLOCK.md`: base Flash-Next Q2 + MTP 1.33x at the 1063 MHz pin, acceptance measured;
- `lowbit-ladder/FINDING_MERGED_CURVE.md`: on the 27B, GSQ-RCO IQ3_XXS sat off the fidelity envelope and unsloth's
  UD-Q2_K_XL was smaller and closer to the reference.

**What this adds:**
- Swift on a sparse MoE, and on a model whose reasoning is already short (base medians 594-753 chars on CAL);
- the first Swift comparison at a matched quant allocation. The 27B and Bonsai pairs relied on the packager's matching;
  here I checked tensor for tensor (below);
- whether the base model's MTP head still drafts for the Swift weights. Swift ships no MTP head ("MTP disabled"), and
  MTP is worth 1.33x to base Flash-Next on this host, so this decides whether Swift is faster *here*;
- as a by-product, GSQ-RCO against unsloth's UD-Q2_K_XL on Flash-Next, the comparison the 27B finding said nobody ran.

## Models

Both are GSQ-RCO IQ3_XXS: a mixed per-tensor allocation (IST Austria's GSQ + RCO), 2 shards, 1,224 tensors.

| arm | repo @ revision | shard sha256 (LFS oid, verified at fetch) | bytes |
|---|---|---|---:|
| **FNGB** base | `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF` @ `ed59f920`, `IQ3_XXS/` | `219ea929…6d15`, `316b46f3…e113` | 75,839,998,528 |
| **FNGS** Swift | `ukisai/Swift-1.5-Qwen3.8-Flash-Next-GSQ-RCO-GGUF` @ `b22d729e` | `3bddaa66…3d23`, `b0b15f78…0160` | 75,966,073,120 |

**The allocations match.** Headers read remotely before download (`tools/gguf_remote_header.py`, range requests):
- the same 1,224 tensor names, and 1,128 identical in type and shape;
- the only difference: the 96 MoE router tensors (`ffn_gate_inp`, `ffn_gate_inp_shexp`, 48 layers each) are F32 in
  Swift and BF16 in ISTA's, 126 MB in all. Routers at higher precision in Swift is the one declared confound;
- `per_layer_token_embd` (28.80 GB, host-resident) is the same type in both, so each puts ~46.9 GB on the GPUs, 3 GB
  less than base UD-Q2_K_XL. Both run fully resident;
- quant fidelity is matched too, per the Swift repo's own table: KLD to each model's own BF16, English prose, 0.116
  (Swift) vs 0.115 (ISTA base).

The quantization procedure is not identical: ISTA refined its own quant; UkisAI reused ISTA's allocation and ran
"Swift-specific GSQ refinement" passes. Both are near their BF16 by the numbers above.

**The Q2_0 tensors are canonical g64 in both files.** All 38 type-42 tensors have offset gaps equal to the g64 row
size (18 bytes per 64 weights) and none equal g128. That is the same test buun's Bonsai detector runs, so its remap
cannot fire.

**The embedded chat templates differ, and the prompts do not.**
- ISTA's template (sha256 `12827f24…`, 9,993 chars) is byte-identical to base UD-Q2_K_XL's: Qwen's plus unsloth's
  fixes (developer role, merged system messages, tool-call argument checks, and `high` silently mapped to `xhigh`).
- Swift's (`c3cf9e34…`, 8,952 chars) lacks those fixes. Asked for `high`, it raises "Unexpected reasoning effort high".
- Rendered offline with jinja2, every request shape this study sends is **byte-identical** under the two templates:
  CAL at xhigh (`3028f9c1e4c8…`), thinking off (`8eb6e577e35d…`), the forced answer slot, no kwargs, and one system
  message. They differ only for `high`, multiple or developer system messages, and tool calls, none of which is sent here.
- The server renders the same: a UD-Q2_K_XL server on .194 returned `3028f9c1e4c8564b` and `8eb6e577e35db705` from
  `/apply-template`. G0 re-checks this on each arm's own server.

## Instrument

- **Host and build:** .194, 4x Tesla P100 at the fleet config (150 W / 1063 MHz, read back in each server's log line),
  buun `0b2789f23` (`~/buun-0b278/build_sm60`), `GGML_CUDA_ALLREDUCE=internal`.
- **Server:** `-ngl 99 -sm layer -ts 1,1,1,0.6 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off`. The `-ts` is the MTP clock
  run's Deviation 1 placement (GPU 3 carries the output layer and the draft buffers); used for every server here so
  that MTP-off and MTP-on share a placement.
- **Discipline (AFM-50):** one fresh verified server per leg: stopped by exact name; its own log says loaded; `/props`
  names the arm's file; `offloaded 49/49 layers to GPU`. One discarded warm-up per server.
- **Gate G0, before any row of an arm.** These files carry **38 canonical g64 Q2_0 tensors**, a format this fleet
  has never decoded on sm_60 (buun has the kernels). A failure of any check stops the arm:
  - the server log must show `type q2_0: 38 tensors` and must **not** show `detected PrismML Bonsai group-128`;
  - at temp 0 with thinking off, the reply to "Count from 1 to 20, separated by commas." must contain exactly the
    integers 1..20, in order, and no other number;
  - `/apply-template` hashes for the CAL-xhigh and thinking-off shapes must equal the base arm's.

  `swift_fn_probe.py` (gate, render, speed) was run end to end on a UD-Q2_K_XL server before registration:
  - coherence passed;
  - the render hashes are as above;
  - decode ran at 20.8 tok/s, which fits Stage B's 21.05.

**Per arm, base first:**
1. **Server A (MTP off).** G0, then the speed probe off, stage 1, stage 2.
2. **Server B (MTP on):** `-md mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3`,
   the base model's head for both arms. Its warm-up must show `draft_n > 0`. Then the speed probe on.

- **Speed probe:** the 6 fixed prompts of `qwen4exp/run_mtp_clock.py`, verbatim (imported), temp 0, thinking off,
  384 tokens, `cache_prompt: false`, run twice. Decode tok/s from server timings; acceptance = accepted / drafted.
- **Stage 1, fibbing with thinking off:** `quant-abstention/run_main.py` on M1 (240 items: 40 E, 100 H, 100 U),
  temp 0, `--expect-variants` (Qwen3.8's UNKNOWN ids, shared by Flash-Next).
- **Stage 2, thinking on:** `run_fixture_structfix.py --tier cal --effort xhigh --sampling card --seed 1001|1002|1003
  --arm A` (the harness of Stage B). Output `swift_flashnext/{FNGB,FNGS}/`.
- **Scoring:** the fixture's grader as registered. AFM-51 (`weber (Wb)` rejected) is reported as a correction
  next to the graded count, as in Stage B, never in place of it.

## Predictions (`analyze_swift_flashnext.py`, committed with this file, self-tested on stored arms)

| # | claim | rule | confidence |
|---|---|---|---|
| F1 | **Swift does not fib less (thinking off)** | Swift - base, U refusal: paired 95 % bootstrap CI lower bound <= 0 | 0.7 |
| F2 | **Knowledge unchanged** | Swift - base, H accuracy: 95 % CI includes 0 | 0.6 |
| F3 | **Swift thinks less where premises are false**, even with short base reasoning | CAL unanswerable: Swift median reasoning chars <= 0.8x base | 0.6 |
| F4 | **Thinking less does not buy honesty** | CAL unanswerable ABSTAINED: Swift <= base (of 24) | 0.6 |
| F5 | **The base MTP head still drafts for Swift** | speed probe acceptance: Swift >= base - 0.10 | 0.5 |

F2 is held at 0.6, below Bonsai's 0.7: this Swift is a real RL + on-policy-distillation fine-tune, and its own card
shows larger drops off GPQA (IFBench -3.1 pp, AIME -2.0 pp).

**Reported without a prediction:**
- NO-STOP counts; CAL answerable; M1 easy; forced-slot P(UNKNOWN); agreement (same grade / same text) on M1;
- decode tok/s off and on, and the MTP speedup, per arm;
- time to answer on CAL, estimated as completion tokens / measured decode rate (an estimate: acceptance measured on
  thinking-off prompts, not in reasoning);
- FNGB against base UD-Q2_K_XL (Stage A `main_FNQ2`, Stage B `FNQ2`): GSQ-RCO vs unsloth on Flash-Next. Same corpus,
  harness, host and build; the Stage A server ran `-c 4096` and no `-ts`, which does not change what a 240-item
  thinking-off pass computes, and the comparison is labelled as cross-session.

**Scope and power:** one quant tier, one seed set. 24 per rate on CAL, so only large honesty effects are detectable;
M1's 100 per group resolves about 0.1. The speed probe is 12 requests per cell.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
