=== MESSAGE 1 ===
Holiday, no rush on any of this — but we kept running with that artifact store thing and learned a fair bit more.

It's not multi-GPU. It's `--split-mode tensor` specifically. Five arms on c9c52d71, Qwen3.5-4B-Q5_K_S, only split mode and device visibility varying:

```
A  -sm tensor  auto split    runtime_pools=2 bindings=0 lanes=0   FAIL
B  -sm tensor  -ts 1,1       runtime_pools=2 bindings=0 lanes=0   FAIL
C  -sm layer   auto split    store ready  lanes=2                 OK
D  -sm layer   -ts 1,1       store ready  lanes=2                 OK
E  -sm layer   1 GPU         store ready  lanes=1                 OK
```

Two things worth flagging there:

- Arm C is two P100s with no explicit split and it binds fine — so "suspected multi-GPU-specific" in my first report was wrong.
- Arm B says the `--tensor-split 1,1` workaround from August doesn't cover this one. Figured you'd reach for that first.

Also correcting myself: I reported `runtime_pools=` as empty. That was my own `cut -c1-185` chopping the line mid-field. Full version:

```
VBR_ARTIFACT_CAPTURE topology unavailable reason=runtime_pool_binding_failed
  devices=2 resolved_split=2 topologies=1 runtime_pools=2 bindings=0 lanes=0 attention_children=1
```

So pools discover fine and then none of them bind. Different subsystem than the one I pointed you at.

=== MESSAGE 2 ===
`2174ad63b` is in this build and still doing its job — `resolved_split=2`. The failure just moved downstream, to `server-context.cpp:8129-8150` where each pool gets matched against `live_device_domains`:

```cpp
return binding.device == pool.backend_device;
```

`runtime_pools=2 bindings=0` means both lookups missed. Your own comment in the August fix is probably the reason:

> Tensor parallelism exposes one meta device to the model loader.

If the pool carries the meta device while the domains list holds the two physical ones, that compare can't hit. Haven't instrumented `pool.backend_device` to confirm, so treat that part as a code read, not a result.

Payoff is real though — same 4010-token prompt sent twice, same binary:

```
-sm tensor   pass1  4010 tok / 4528 ms    pass2  4010 tok / 4527 ms
-sm layer    pass1  4010 tok / 4784 ms    pass2     4 tok /   51 ms
```

We're staying on `-sm tensor` regardless — layer split is inert across two P100s (8.54 vs 13.93 t/s decode), so it'd cost us 39% to dodge this. Rather wait for the real thing.

Repro is just about any model with `-ctk vbr -ctv vbr --vbr-floor t4 --cache-ram 4096` under `-sm tensor` on 2 GPUs. And zero guard rejections anywhere in these logs — no `currency_changed`, no `unsupported_layout` — so it looks unrelated to #121.
