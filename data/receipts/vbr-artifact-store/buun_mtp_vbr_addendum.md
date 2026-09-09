**Addendum — isolated it. The VBR clamp is benign; MTP's reaction to it is the defect.**

Re-ran the identical config with `--spec-type` omitted. Same build `3823c9eb6`, same model, same `-ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto`. Only the draft head is gone.

**The clamp still fires:**
```
19.09  tg_3s = 27.67
19.11  W prepare_with_slots: VBR budget 5442.49 MiB exceeded with the degrade order
         clamped at the --vbr-floor (projected 160.38 MiB at 18176 cells)
19.12  tg_3s = 27.35
19.15  tg_3s = 27.70
```

**And it does nothing.** Decode across the clamp, measured on progress lines so incomplete requests are included (completion-only sampling can't see post-clamp behaviour):

| | n | median | p10 | p90 |
|---|---|---|---|---|
| before clamp | 289 | 27.3 t/s | 26.8 | 27.7 |
| after clamp | 50 | 27.5 t/s | 27.4 | 27.6 |

**0.99×.** Run continued normally, no wall.

| condition | clamp fires | result |
|---|---|---|
| VBR + MTP | yes | acceptance → 0.000, `mean len` 1.00, decode 2.7× slower, permanent |
| VBR, no MTP | yes | decode unchanged, run continues |

So the restated defect is narrower than what I sent before:

> **When the VBR degrade order clamps at `--vbr-floor`, the MTP draft head permanently stops producing acceptable drafts (`acceptance 0.000`, `mean len 1.00`) for the life of the server. The clamp itself is harmless — with `--spec-type` omitted the same clamp fires with no measurable effect on decode.**

This is a better control than the `-ctk f16 -ctv f16` arm I offered earlier: VBR and the clamp stay fully present, only MTP is removed, and the harm disappears with it. No ambiguity about whether VBR or the checkpoint machinery is implicated.

Still true from before: restart fully restores acceptance (0.000 → 0.93–0.97, decode 22 → 60 t/s on an identical prompt), and 80 pre-clamp requests never fell below 0.444 acceptance while every post-clamp one was ≤ 0.312.
