# buun master on Pascal: qwen4 passes, NCCL AllReduce hard-aborts, grok test broken everywhere

**2026-09-02.** `.194`, 4x Tesla P100-PCIE-16GB (sm_60) @ **150 W / 405 MHz idle**, CUDA 12.4,
gcc-15 with `-allow-unsupported-compiler`. `spiritbuun/buun-llama-cpp` master `7a918624b`,
built fresh as `build_sm60_qwen4`. First Pascal datapoint on this tree — buun develops on a 3090.

## 1. It builds clean for sm_60

`cmake -DCMAKE_CUDA_ARCHITECTURES=60 -DLLAMA_BUILD_TESTS=ON`, targets `llama-server` +
`test-llama-archs`. **Zero compile errors**, 13 minutes wall. No Pascal-specific patching needed.

## 2. The qwen4 work PASSES on Pascal

From `test-llama-archs`:

```
Qwen4 sparse asymmetric Turbo8 K/F16 V NMSE 0, F16 K/Turbo8 V NMSE 4.26e-17
Qwen4 selected-cell gather Turbo8 K/V NMSE 0/1.33e-16, scan parity 1.57e-14,
   streams 0/0, dormant 0, unified fork 0/0
Qwen4 static Turbo and dynamic dense/sparse QSA VBR CUDA test PASSED
Qwen4 MTP standalone sidecar/target handoff contract test PASSED
```

NMSE at or below 1e-16 — the QSA/VBR/MTP paths behave on sm_60. This is the headline: buun's
41–53 tok/s numbers are 3090-only claims, but the *correctness* of the path is now confirmed on
hardware he does not have.

## 3. BUG — NCCL AllReduce hard-aborts on multi-GPU P100

With the default comm chain the suite **dies at the first Meta (multi-device) row**:

```
| llama | Meta | Dense | CUDA error: unhandled cuda error ...
   device=1; function=ggml_backend_cuda_comm_allreduce_nccl;
   ggml-cuda.cu:1126; statement=ncclAllReduce(...)
ggml-cuda.cu:126: CUDA error
```

Process aborted (rc=134). **It does not fall through to the next backend in the chain** — it
kills the run.

### Isolated by A/B/C

| arm | comm path | rc | arch rows reached | died at |
|---|---|---|---|---|
| **A** default (nccl first) | NCCL | **134 abort** | **10** | `llama` Meta |
| **B** `GGML_CUDA_ALLREDUCE=internal` | internal -> butterfly | 255 | **31** | `grok` (see §4) |
| **C** `CUDA_VISIBLE_DEVICES=0` | none | 255 | 24 | `grok` (see §4) |

Arm B clears the Meta rows outright (`baichuan | Meta | OK (2.86e-14)`), so **the NCCL call is
the cause, not multi-GPU in general.** Workaround is one env var.

Consistent with [[allreduce-internal-inert-on-pascal]]: internal AllReduce requires cc >= 700 and
silently falls back to butterfly on sm_60. The NCCL path, by contrast, fails **loudly and
fatally**. The chain is documented as `nccl -> internal -> none`, each step warning and recursing
on failure; that graceful degradation does not happen when NCCL raises a CUDA error mid-call
rather than failing at init.

## 4. BUG — `grok` arch test fails on ALL hardware, including CPU

Both surviving arms stop at the same place:

```
grok | MoE | error loading model hyperparameters:
   key grok.embedding_scale has wrong type u32 but expected type f32
```

**Reproduced with `CUDA_VISIBLE_DEVICES=""` (CPU only)** — so this is not Pascal, not CUDA, and
buun will see it on his 3090. It means `test-llama-archs` does not currently pass on master on any
hardware. The synthetic fixture writes `embedding_scale` as u32; the loader demands f32.

For contrast, Tom's turboquant tree at `85eb0596a` ran the same suite to **rc=0, 458 OK rows**
(`data/receipts/qwen4exp/RESULT_85eb0596a_DS4.md`), so this is specific to buun's tree.


## 5. Flash-Next generates coherently on Pascal — control for jabba's report

Prompted by jabba (Discord, 2026-09-02): *"qwen3.8-flash fails completely for me, generates
gibberish or nothing at all, other models ... work just fine."* **Single GPU** (confirmed by Mark),
running buun's tree, no `-ctk`/`-ctv` so default f16 KV.

Same quant he uses (`Qwen3.8-Flash-Next-UD-IQ4_XS`, 87.2 GiB, 3 shards), this build, 4x P100,
`-c 8192 -ngl 99 -fa on --jinja -np 1 -fit off -ncmoe 24`, shipped chat template, temp 0:

> The capital of France is Paris. It is historically significant as a major center of European
> politics, culture, and intellectual life, playing key roles in events such as the French
> Revolution and the development of modern democratic ideals...

`reasoning_content` separated cleanly; `finish_reason: stop`; 102 completion tokens. Model loaded
in 2 min 33 s, VRAM 2441 / 2611 / 15531 / 15209 MiB.

**So the model, the quant, and buun's build are all sound on Pascal.** Whatever jabba is hitting
is in his flag set, not the arch or the tree.

### Differences between his line and this control, ranked

| # | his flag | ours | why it matters |
|---|---|---|---|
| 1 | `-c 512000` | `-c 8192` | GGUF says `qwen4exp.context_length = 262144` and carries **no rope-scaling metadata**. 512k is 1.95x native with no YaRN configured. |
| 2 | `--chat-template-file .../qwen3.6-chat-template/` | shipped template | The GGUF ships its own multimodal template. Special-token sets match (both `<\|im_start\|>`/`<\|im_end\|>`), so not catastrophic on that axis, but the 3.8 template has its own reasoning/tool structure and a `render_content` macro. |
| 3 | `-b 8192 -ub 2048` | defaults | Batch shape is known to change numerics on this fleet (`hermesagent20/PREFIX_CACHE_CHANGES_OUTPUT.md`); large ub through the QSA path is untested. |
| 4 | `--load-mode none` | unset | buun-specific; unexamined here. |

Single GPU rules out the `head_count_kv` zero-width-slice failure entirely — that requires
`-sm tensor` with more devices than KV groups, and Flash-Next has `head_count_kv = 2`.


### Bisect outcome — four hypotheses falsified, one strong candidate left

| hypothesis | status |
|---|---|
| `head_count_kv` zero-width slices | **dead** — jabba is single-GPU (confirmed); needs `-sm tensor` + devices > KV groups |
| missing Turbo K/V unrotation | **dead for jabba** — he runs buun's tree with no `-ctk`/`-ctv`, so f16 KV. Still a live gap in *Tom's* fork. |
| `-c 512000` vs native 262144 | **dead** — jabba reports the same failure at `-c 8192` |
| `--chat-template-file` 3.6 override | **dead** — tested as a single variable on our box, coherent output |
| **stale build predating buun's fixes** | **open, and most likely** |

buun announced qwen4 support on 08-30 ~21:10. Five commits landed after, four of them qwen4
correctness/hardening fixes, the last on 09-01 19:22. A build made on the announcement is missing
`295850adc` (Turbo V unrotation), `fd56dfcdd` (adaptive caching / long-context), `6a2eb3232`
(recurrent PLE speculative resize) and `0f6a7267a` (Turbo K unrotation after QSA gather). The two
`fix(qwen4)` commits are both "output is wrong" bugs of exactly the reported shape.

Our control build is `7a918624b` and contains all of them — which is consistent with it working.
Not yet confirmed: jabba has not reported his commit.

### Method note — three harness bugs in one session, all from SSH quote nesting

Recorded because the pattern matters more than the instances. (a) pinned `CUDA_VISIBLE_DEVICES=0,1`
for an 87 GiB model and read the resulting `unable to allocate CUDA0 buffer` as a model failure for
a moment; (b) quote-stripping through a nested heredoc silently rewrote the readiness probe
`grep -q '"status":"ok"'` into `grep -q status:ok`, which can never match — the server was ready
for minutes while the harness waited; (c) the same nesting broke an inline Python parser.

None corrupted a result — each failed loudly — but (b) is exactly the readiness-probe failure class
[[readiness-probes-lie]] warns about, self-inflicted. **Fix: write scripts to a file and `scp` them,
never heredoc through three quoting layers.** Done correctly earlier the same day for `logmap.py`;
abandoned under time pressure.

## Not claimed

No throughput measurement. buun's 41.6 / 53 tok/s figures are untested here and are 3090 numbers;
nothing in this receipt speaks to them. No model was loaded beyond the suite's synthetic fixtures.
Correctness and build only.
