# DRAFT 2 — short UPDATE for Tom's thread (follows the report Mark already posted). NOT POSTED.

---

Follow-up on the `-sm tensor` part. The failure isn't "3 or more devices" — it's **more devices
than KV groups**, and I can now show it predicts successes as well as failures.

Dense attention splits into exactly `head_count_kv` units. Holding the binary (`c232282aa`), the
box (4x P100) and the flags (`-ngl 99 -sm tensor -np 1 -c 4096`) fixed, and varying only the
model:

| model | arch | `head_count_kv` | 2 dev | 3 dev | 4 dev |
|---|---|---|---|---|---|
| synthetic `test-llama-archs` (`head_count_kv = n_head = 2`) | qwen3next | 2 | ✅ | ❌ abort | ❌ abort |
| Flash-Next Q2_K_XL | qwen4exp | 2 | ✅ | ❌ garbage | ❌ garbage |
| Qwen3.8-27B-UD-IQ4_XS | qwen35 | **4** | — | — | ✅ **coherent** |

The 27B row is the one I'd point at, because the rule predicted a **success** and got one:

```
vram: 3701 / 3701 / 3701 / 3701 MiB    (exactly even)
util:   56 /   55 /   51 /   55 %      (all four concurrent)
GEN : ' Paris.\nThe capital of Germany is Berlin. ...'
15.39 tok/s @ 40 tok, 15.41 @ 80
```

`12288 / (2 * n_gqa * n_embd_head_k)` = `12288 / (2*6*256)` = 4 units, one per card. Flash-Next
has 2 units, so device 3 onward gets `ne = 0`.

That's also the first *valid* tensor-split throughput number I have — the Flash-Next figure I
mentioned earlier came from a run emitting `////`, so I'm withdrawing it as a measurement.

**Scope caveat so this doesn't get over-applied:** the rule is for architectures that split dense
attention by KV group. It does **not** cover MLA — `deepseek4` has `head_count_kv = 1` but never
reaches that path, since it has its own `attn_q_a`/`attn_kv` MIRRORED and `attn_q_b` -> paired
patterns.

Which leads to something you may already know: back on 2026-08-01, on `8a891f4b5`, I tried DS4
Flash under `-sm tensor -ts 3,4,4,1` on these same four cards and every arm aborted with

```
GGML_ASSERT(src_ss[0].axis != GGML_BACKEND_SPLIT_AXIS_0) failed
```

That was also an under-provisioned case (1 KV group, 4 devices), just a different assert on much
older code. If the dedicated DS4 patterns now in `c232282aa` were added for that, the same
approach — mirror, or place on a subset — might be what the GQA path needs when the unit count
runs out. **Happy to run DS4 tensor-split on `c232282aa` and report**, if that datapoint is
useful to you.

The thing I'd flag as most important: the granularity itself is load-bearing and shouldn't be
narrowed. `lcm(2*n_embd_q, blck_size_perf)` keeps a whole KV group on one device; shrinking it to
make the division come out even would split a KV group across cards and produce the same garbage
tokens by a different route.
