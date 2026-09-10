# Qwen3.8-27B vision works, and the F16 projector sidesteps the Pascal problem

**2026-08-29**, control plane RX 9070 XT (gfx1201, ROCm/HIP), `moe-cache-test` HIP build.

## The projector exists, in two precisions

`unsloth/Qwen3.8-27B-GGUF` ships **both** `mmproj-BF16.gguf` and **`mmproj-F16.gguf`** (927 MB).
Nothing for Qwen 3.8 was on the NAS — the only projectors there are Qwen 3.6 (27B, 35B-A3B),
Gemma 4 12B and Crow-9B, all **BF16**.

**F16 is the one to use on this fleet.** BF16 is not native below `sm_80`; P100 is `sm_60` and does
**F16 at 2:1**. Taking the F16 variant removes the BF16-on-Pascal question rather than testing it.

## It works, first try

```
llama-server -m Qwen3.8-27B-UD-IQ2_M.gguf \
  --mmproj qwen38-mmproj/mmproj-F16.gguf -ngl 99 -c 8192 -fa on --jinja
-> srv load_model: loaded multimodal model  (ready in 14 s)
```

Test image (448x448, generated so the content cannot be guessed): red circle top-left, blue
rectangle top-right, yellow triangle bottom-centre, text `APOLLO 47`.

Model output, temp 0:

```
APOLLO 47

Red circle in the top left.
Blue rectangle in the top right.
Yellow triangle in the bottom center.
```

**Every element correct, including the exact text** — which is the part that cannot be bluffed from
a generic "geometric shapes" prior. 28.1 tok/s, 270-token prompt, on a **9.61 GiB IQ2_M** quant.

Vision survives IQ2 weights on this architecture, at least for shape/colour/position/OCR at 448px.

## For the `.73` phone workflow

Adding vision there is **additive, not a downgrade** — the Q6_K LLM stays, the projector is an extra
`--mmproj` flag:

| | |
|---|---|
| current `.73` usage | ~12.0 / 12.4 GiB of 16 GiB per card, Qwen3.8-27B-Q6_K @ `-c 262144` |
| projector cost | **+0.93 GiB** |
| projected | ~13.4 GiB per card — fits, but wants confirming under the 262k KV |

Steps if wanted: copy `mmproj-F16.gguf` to `.73`, add `--mmproj <path>` to `WP_START_CMD` in
`apollo-wake-proxy.service`, restart the proxy. Fully reversible; the flag is the only change.

**Untested:** the projector on `sm_60` specifically, and whether it fits alongside a 262k KV cache.
Mark recalls running Qwen 3.6 vision on Pascal successfully, so the arch path is likely fine.

---

# Deployed to `.73` and cold-tested (2026-08-29)

## Cost to the VBR budget, measured

Mark's framing was the right one: with `--vbr-vram auto` the projector does not displace KV, it
shrinks the pool VBR resolves into — so the cost appears as **earlier tier degradation at depth**,
not as a fit failure. A/B on `.73`, same model, same `-c 262144`, projector the only variable:

| | GPU0 | GPU1 |
|---|---|---|
| baseline | 11607 MiB | 11973 MiB |
| with `--mmproj` | **12775 MiB** | 12005 MiB |
| delta | **+1168 MiB** | +32 MiB |

**The vision tower loads entirely on GPU0 — it is not split.** Free space becomes asymmetric
(3609 MiB GPU0 vs 4379 MiB GPU1), so GPU0 reaches the t2 floor (2.25 bits/value) earlier under
deep context. Both legs held `n_ctx = 262144`.

## A wake race, found by testing rather than assuming

The first cold cycle after deployment **failed**:

```
11:48:32 wake: node up after 10s
11:48:32 start: launching llama-server
11:48:32 start: launch command failed rc=255:
         kex_exchange_identification: read: Connection reset by peer
```

`wake()` returns as soon as **one** ssh succeeds; `start_server()` then immediately opens a
**second**, and sshd is not reliably ready that instant after S3 resume — it accepts TCP and resets
during key exchange. Intermittent, which is worse than deterministic: every previous cold cycle had
happened to win the race.

**Fix:** retry the launch ssh up to 3 times with 5 s backoff. The reasoning is sound because
`start_cmd` backgrounds the server, so **a non-zero rc is always an SSH-transport failure, never a
bad llama-server flag** — a broken command still exits 0 and is caught later by the liveness probe
added on 2026-08-28.

## Verified end to end

```
11:49:19  .73 suspended
11:49:30  wake: sending magic packet
11:49:41  wake: node up after 10s
11:50:35  start: /health OK after 54s
```

Image request through the proxy, **97.9 s cold**:

> The exact text in the image is **APOLLO 47** (located in the bottom left corner).
> The shape in the top left is a **circle** (red).

Both correct, including the corner. Vision now works over the full path: sleeping node -> WoL ->
cold load with projector -> multimodal answer.

---

# The first real phone image failed — and the model had already answered

**2026-08-29 ~11:54.** Mark sent a photo from hermes-go. The GUI appeared to hang; he backed out
and reloaded, and the session desynced into two unanswered messages.

## `.73` answered in full. The reply was lost in transit.

Server log, task 151:

```
3:59.038  launch_slot: task 151 processing
          edit/divergence (cached/incoming/lcp/reusable/...) = (450/16028/3/3/447/16025/1)
5:50.861  prompt processing, n_tokens = 16024, t = 111.82 s / 143.30 tok/s
6:29.381  n_decoded = 284, tg = 7.68 t/s
6:30.297  release: stop processing: n_tokens = 16318, truncated = 0
```

| | |
|---|---|
| image -> prompt tokens | **16,025** (from a 28 KB JPEG) |
| prompt processing | **111.8 s** @ ~143 tok/s on 2x P100 |
| generation | 284 tokens @ 7.68 t/s (~37 s) |
| **total** | **~151 s** |
| reusable from cache | **3 tokens of 450** — image turns do not prefix-cache |

The screenshot is stamped 11:57; the server released at ~11:57:05. **He gave up seconds before it
finished.** A complete 284-token answer was generated and discarded.

## Root cause: 112 seconds of total silence

`llama.cpp` emits nothing during prefill. Our proxy only sent SSE keepalives while **waking** —
once the node was up it proxied straight through, so a long image prefill is byte-for-byte
indistinguishable from a hang. The wake case was designed for (77-99 s cold start); the
**image-prefill** case was not.

## Fix: keepalive until the model's first byte

The streaming branch now races each upstream chunk against a 10 s timer and emits `: processing`
SSE comments while the model is silent — not just while the node is waking.

**Verified** with Mark's actual photo through the proxy:

```
[  10.2s] keepalive #1
[  27.5s] FIRST MODEL TOKEN
keepalives sent : 2      total elapsed : 42.6 s
```

> "A crescent moon glows against a completely black night sky, its illuminated right side
> revealing the gray patches of lunar maria and scattered craters."

Correct, and no client-side TTFB timer can arm now.

**Caveat:** this only helps **streaming** clients. A non-streaming request still returns one JSON
body at the end, and nothing in a proxy can shorten that — for images on this hardware that is a
~150 s wait. If hermes-go sends image turns non-streaming, that is the remaining exposure.

## CORRECTION — "silent confabulation" was wrong

I initially read a no-vision image turn (~2.1k prompt tokens instead of ~16k) as the model
inventing a description. **It was not.** With the vision tool unavailable it announced the
limitation — *"my vision tool isn't available in this session"* — and fell back to **file-level
analysis via code execution**. Checked against the actual bytes of
`upload_20260829_120401_1.jpg`:

| model claimed | measured |
|---|---|
| 2048x1153 JPEG | **2048x1153** |
| Samsung SM-G998U1 | **samsung SM-G998U1** |
| Aug 27 2026 | **2026:08:27 23:18:15** |
| GPS present but zeroed | **`(0.0, 0.0, 0.0)`** |
| ~91% pure black | **91.1%** |
| bright cluster x 616-1112, y 284-704 | **x 638-1111, y 283-673** |

Every claim correct; the bbox differs only by luminance threshold. So the token-count signal
(~16k vs ~2k) reliably distinguishes **vision** from **no vision**, but it does **not** imply
the answer is fabricated — the model may have genuine file access instead. Two different
capabilities, and the prompt-token count only measures one.

## Third hermes-go finding for O7 — LOCATED (2026-08-29, Mark's diagnosis)

Mark worked out the mechanism: attaching an image uploads it to the **gateway host** at
`~/.hermes/images/upload_<ts>_<n>.jpg`, and the message carries `@image:<path>`. Interrupting
generation converts the turn to that text form.

The gateway code shows this is a **regression against stated intent**, not the design.
`tui_gateway/server.py:_build_persist_user_message`:

> "Native-vision turns send `content` as a parts list ... So mirror the shape: replace only the
> text part with the `@image:` ref form and **keep the image parts, so the model still has the
> pixels for the rest of the session**. Any API-only text part (**the barge-in note**) is dropped
> along the way, which is the point of the override."

So `@image:` is meant to be a **display/persistence** form sitting *alongside* retained image
parts. The barge-in (stop-mid-generation) path is losing the image parts and persisting only the
string form — after which the model receives a **filesystem path as text** rather than pixels.

**This is in the Python gateway, not the mobile app** — a different component from the dedup fix.

Signature, server-side: **~16k prompt tokens** (pixels present) vs **~2k** (path only).

**Not a security issue:** `agent/context_references.py` guards resolution with `allowed_root`,
`resolve()`, and home / `hermes_home` checks (lines 251-255, 475-487). Checked before raising it.

**Housekeeping note:** `~/.hermes/images/` accumulates uploads with no visible eviction — 4 files
today. Small now (112 KB), but unbounded on a phone-heavy workflow.

## Original framing of the third finding

The reload produced **two** messages, and the second **lost the image attachment** — the first
carries `@image:/home/mark/.hermes/images/upload_20260829_115318_1.jpg`, the second is bare text.
So a resend after reconnect does not re-attach the image. Note this is about the **attachment
reference being dropped**, not about the model fabricating — see the correction above. Joins the
dedup and stale-metadata findings.

---

# MTP enabled on `.73` — 1.83x for free (2026-08-29)

Mark: *"3.8 from most providers has it built into the main file now."* Correct, and it removes the
whole draft-model question. `Qwen3.8-27B-Q6_K.gguf` carries the MTP head **inside the main GGUF**:

```
qwen35.nextn_predict_layers = 1
blk.64.nextn.eh_proj.weight            [10240, 5120]
blk.64.nextn.enorm.weight              [5120]
blk.64.nextn.hnorm.weight              [5120]
blk.64.nextn.shared_head_norm.weight   [5120]
```

`block_count = 65`, so **block 64 is the MTP layer**. No `--spec-draft-model`, no extra weights,
no extra VRAM. (Staging `.194`'s separate `mtp-Qwen3.8-27B-Q4_0.gguf` was wasted effort — and
failed anyway, `.194 -> .73` has no key trust.)

## Result

Added `--spec-type draft-mtp --draft-max 3` to `WP_START_CMD`. Same model, same context, same VBR
settings, identical prompt, temp 0:

| | tok/s |
|---|---|
| baseline | 7.96, 7.97 |
| **MTP depth 3** | **14.57, 14.67** |
| | **1.83x** |

Engagement confirmed from the server log, not inferred:

```
slot load_model: speculative decoding context initialized
draft acceptance = 0.72973 (81 accepted / 111 generated), mean len = 3.19
verify/rollback histogram (draft/rejected:cycles) = (3/0:21, 3/1:7, 3/2:4, 3/3:5)
```

**73% acceptance**, and 21 of 37 cycles took the full 3-token draft with nothing rejected. A
community report on a 5090-class card using an *external* MTP draft model measured ~49.5%
acceptance; the embedded head on Pascal is doing better than that here.

Depth 3 chosen because `--draft-max` defaults to 3 and `RESULT_S2_DFLASH_PASCAL` found MTP on
Pascal **peaks at n=3**, going *slower than not speculating* by n=15. Higher depths are not worth
trying on this hardware.

Benefits every consumer of `.73`: the phone, Hermes Desktop, and the ledger's 3-hourly run.

## Then Mark asked "tensor or layer split?" — another 1.6x on top

`.73` had no `-sm` flag, i.e. **layer split by default**. But the same-day `llama-bench` run on
`.194` (identical 2x P100, identical Qwen3.8-27B-Q6_K) measured **7.83 layer vs 13.20 tensor**,
and `.73`'s layer baseline was 7.96 — the same number. So the box had been leaving ~1.7x on the
floor.

Qwen3.8-27B has `head_count_kv = 4` and `.73` has 2 devices, so `n_devices <= head_count_kv` and
the zero-width-slice class we spent the day on cannot trigger here.

Added `-sm tensor`. Cumulative on `.73`, same model / context / VBR / prompt, temp 0:

| config | tok/s |
|---|---|
| layer split (as it had been running) | 7.96, 7.97 |
| layer + MTP depth 3 | 14.57, 14.67 |
| **tensor + MTP depth 3** | **22.52, 23.76, 26.22** |
| | **~3x over baseline** |

Verified **correct**, not just fast — `17 x 23 = 391`, capital of Portugal = Lisbon — because
tensor split's failure mode today was fluent garbage, not an error. Draft acceptance held at
0.70-0.78. VRAM 13831 / 12695 MiB, no aborts, and the documented quantized-KV x tensor-split
abort (N6) did **not** occur with `vbr`/`vbr` on the buun build.

Two flags, no extra VRAM, no new model files: **7.96 -> ~24 tok/s.**
