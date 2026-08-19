# VBR causes it: f16 survives the identical sequence, VBR collapses on the first request

**2026-08-19**, control plane **RX 9070 XT (gfx1201, RDNA4, ROCm/HIP)**, buun `02f8581`
`build_rocm`, `Qwen3.8-27B-AD-IQ2_S.gguf`, `-ngl 99 -c 16384 --jinja`, `n_predict 3072`,
temp 0, top_k 1. Script `f16_control.py`, logs `ctl_f16.log` / `ctl_vbr.log`.

Both arms run **back to back in one script**, same ten items in the same order, with a
known-good canary before and after each. **The KV codec is the only variable.**

## Result

| | `-ctk f16 -ctv f16` | `-ctk vbr -ctv vbr` |
|---|---|---|
| canary **before** | **ok** (141 ch) | **ok** (162 ch) |
| T2-01 … T2-10 | **10/10 clean** — 422-706 chars each, `finish=stop` | **10/10 collapsed** — 3072 chars, `!frac=1.00`, `finish=length` |
| answers correct | **9 / 10** | 0 / 10 |
| canary **after** | **ok** (141 ch) | **DEAD** (`!frac=1.00`) |
| first collapse | **none — arm survived** | **T2-01, the very first item** |

**f16 answers the same questions in 422-706 characters and is still healthy afterwards. VBR
passes its pre-canary, then emits 3,072 `!` characters to the first real request and never
recovers.**

## What this settles, and what it does not

**Settles:** the collapse is **not** IQ2_S weights, **not** the HIP backend, **not** the
prompt template, **not** the items, **not** the token budget, and **not** the server harness.
All of those are identical across the two arms. It is the **VBR KV path**.

Eleven hypotheses had been eliminated before this by ad-hoc probing (see
`OPEN_IQ2S_SILENT_COLLAPSE.md`), and **every one of them had assumed VBR was involved without
ever testing it.** One control settled in twenty minutes what ten guesses could not.

**Does not settle:** *why*. No degrade event ever fired (`degrade #` count zero in every log),
the auto-budget was 4304-4312 MiB in all six servers — healthy and collapsed alike — and
collapse has occurred at generation depths as low as 1536 tokens while 2048-token essay
generations survived. **The trigger inside VBR is unknown.**

## Why it is nastier than a crash

- **Silent.** HTTP 200. `finish_reason: length` — the model is "successfully" generating, it
  is just generating `!` until it hits the cap.
- **Total and permanent.** Once one request collapses, every subsequent request does, until
  the process restarts.
- **Invisible to every quality metric we own.** Throughput stays ~27 t/s. The fidelity panels
  measure teacher-forced KL against a reference and never sample free generation. A KLD panel
  would call this server healthy.
- **Caught only by the tier-1 gate**, five trivial questions written ninety minutes earlier.

## Minimal reproduction

```bash
llama-server -m Qwen3.8-27B-AD-IQ2_S.gguf -ngl 99 -c 16384 \
             -ctk vbr -ctv vbr --jinja --host 127.0.0.1 --port 8080
# short request: fine
curl -s localhost:8080/v1/chat/completions -H 'Content-Type: application/json' -d \
 '{"messages":[{"role":"user","content":"What is 17 multiplied by 23? Reply with just the number."}],
   "temperature":0,"top_k":1,"n_predict":256}'
# then a reasoning request with a large budget: 3072 '!' characters, and the server is dead
curl -s localhost:8080/v1/chat/completions -H 'Content-Type: application/json' -d \
 '{"messages":[{"role":"user","content":"A tank fills at 4 L/min and drains at 1.5 L/min. It starts at 20 L and holds 200 L. How many minutes until it is full?\n\nThink briefly if you need to, then end your reply with exactly one line:\nExact Answer: <your answer>"}],
   "temperature":0,"top_k":1,"n_predict":3072}'
```

Swap `vbr` for `f16` and it answers in ~479 characters, correctly, every time.

## Caveats before this goes anywhere

- **One model, one quant, one backend.** `AD-IQ2_S` on gfx1201/HIP. Untested on CUDA, on
  other quants of the same model, and on other models. It may be an interaction with 2-bit
  weights rather than a VBR defect in general — **the arm that would separate those is VBR at
  a higher weight quant, and it has not been run.**
- **Not intermittent within an arm, but arm-onset is not fully characterised** — earlier
  sessions ran many VBR requests before collapsing, this one collapsed on the first.
- **`VBR_BUDGET_MIB` was auto**, not pinned. Whether pinning changes it is untested, and is
  the obvious next arm given the auto value derives from `hipMemGetInfo`, which this same
  session measured to be wrong by 2.4 GiB on this machine.
