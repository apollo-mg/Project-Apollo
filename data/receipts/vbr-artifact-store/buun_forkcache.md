=== MESSAGE 1 ===
Followed that up — it's specific to your fork, and there's a working reference point in your own history.

Same node, same model, same prompt sent twice, minimal flags all three binaries accept (`-ngl 99 -c 32768 -np 1 -fa on -ctk f16 -ctv f16`). Pass 2 prefill token count, 4010 = no reuse:

```
                          -sm tensor    -sm layer
upstream 34af94c (Aug17)      4 tok        4 tok
tom      f6124e9 (Aug17)      4 tok        4 tok
buun     c9c52d71          4010 tok        4 tok
```

Five of six cells reuse. Only your fork under tensor split doesn't.

And it isn't a VBR thing at all — f16, q8_0, q8_0+turbo3 and vbr *all* re-prefill under `-sm tensor`, and all reuse under `-sm layer`. VBR is just the only one that says anything: f16 and q8_0 emit no warning whatsoever and silently re-prefill forever. That's probably the bigger deal, and it's why I'd deprioritise the artifact store as the framing.

=== MESSAGE 2 ===
Bisected with buun builds already sitting on the box, no rebuilds needed:

```
2026-07-26   10442 (a8e5b5a38)    pass2   516 tok   <- reuses 3494 of 4010
2026-08-25   531 (e332b24)        pass2  4010 tok
2026-09-06   979 (c9c52d71)       pass2  4010 tok
```

So it worked in July and was gone by Aug 25 — a regression with a working reference point, not something that never landed. That window is also a month before your Sep 2 upstream sync (`a71ca2fd2`), which rules out inheriting it from upstream.

The Aug 25 build's HEAD is `e332b2494 "dflash: harden checkpoint rewind lifecycle"`. Flagging that as the **build boundary only**, not a suspect — I couldn't narrow inside the window because `a8e5b5a38` isn't in my clone anymore.

Everything in the earlier message still holds, it's just scoped narrower than the bug actually is. Happy to run anything else you want on the 2×P100 box.
