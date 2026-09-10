# DRAFT — report for buun. For Mark to review. NOT SENT.

---

Built your master (`7a918624b`) for Pascal sm_60 on the 4x P100 box. Good news first: **it builds
clean with no patching, and the qwen4 work passes.**

```
Qwen4 sparse asymmetric Turbo8 K/F16 V   NMSE 0, F16 K/Turbo8 V NMSE 4.26e-17
Qwen4 selected-cell gather Turbo8 K/V    NMSE 0 / 1.33e-16, scan parity 1.57e-14
Qwen4 static Turbo + dynamic dense/sparse QSA VBR CUDA test   PASSED
Qwen4 MTP standalone sidecar/target handoff contract test     PASSED
```

CUDA 12.4, gcc-15 with `-allow-unsupported-compiler`, `-DCMAKE_CUDA_ARCHITECTURES=60`. 13 minutes.
Since you're on a 3090 I figured a Pascal datapoint was worth having.

Two bugs, one of which you can check in thirty seconds on your own box.

## 1. `grok` arch test fails on ALL hardware, including CPU-only

```
grok | MoE | error loading model hyperparameters:
   key grok.embedding_scale has wrong type u32 but expected type f32
```

I reproduced this with `CUDA_VISIBLE_DEVICES=""`, so it isn't CUDA, isn't Pascal, and should
repro for you directly. `test-llama-archs` doesn't currently get past `grok` on master. Looks like
the synthetic fixture writes `embedding_scale` as u32 while the loader wants f32.

## 2. NCCL AllReduce aborts the process on multi-GPU P100 instead of falling back

With the default comm chain the suite dies at the first Meta row:

```
| llama | Meta | Dense | CUDA error: unhandled cuda error
    device=1; function=ggml_backend_cuda_comm_allreduce_nccl
    ggml-cuda.cu:1126; ncclAllReduce(...)
ggml-cuda.cu:126: CUDA error   ->  abort, rc=134
```

Isolated it three ways:

| arm | comm | result | arch rows reached |
|---|---|---|---|
| default | NCCL | **abort (134)** | 10 |
| `GGML_CUDA_ALLREDUCE=internal` | internal -> butterfly | runs on | **31** |
| `CUDA_VISIBLE_DEVICES=0` | none | runs on | 24 |

With `internal` the Meta rows pass outright (`baichuan | Meta | OK (2.86e-14)`), so it's the NCCL
call specifically, not multi-GPU.

The thing I'd flag: the chain is meant to be `nccl -> internal -> none`, each step warning and
recursing on failure. That works when a backend fails at **init**. Here NCCL initialises fine and
then raises a CUDA error **mid-call**, which goes straight to `GGML_ABORT` with no fallback. On
Pascal that's the difference between "slower comm path" and "the process dies".

Related, and possibly useful context: on sm_60 the *internal* AllReduce can never engage either —
`ggml_cuda_ar_pipeline_init` requires cc >= 700 because the chunked kernel uses `__nanosleep`. It
falls back to butterfly correctly and silently. So every Pascal multi-GPU run is on butterfly, and
NCCL is the only comm path that turns a fallback into a crash.

Happy to test whatever you'd like on this box — it's the only 4x P100 rig around and I'm not using
it for anything else this week.
