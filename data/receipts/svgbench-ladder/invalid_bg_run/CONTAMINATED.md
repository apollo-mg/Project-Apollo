# CONTAMINATED — do not use for any result

Run started 2026-09-10 18:42, stopped 19:05 after the first complete rep.

**Cause:** `svg_probe._ink()` took the median of the four corner pixels as the single background
colour. The first drawing (UD-Q2_K_XL rep 1) had sky at the top and ground at the bottom; the
corner median, rgb(186,208,203), matched neither, and **99.7% of the canvas registered as ink.**

**Consequences, all invalid:**
- The feedback grid sent to every correction step was a solid block of `@`. Both the intent and
  goal fault lists say so explicitly ("every cell is `@` ... except two stray `%` marks").
- Structural scores were computed on a near-total ink mask: p1 scored 6/11 and stayed 6/11 through
  all four passes with a single component — a genuinely well-assembled drawing (neck attached,
  pouch, legs on pedals, sun, clouds, speed lines) marked mediocre.
- Correction steps received no usable information, so they measure nothing about feedback use.

The p1 SVG itself is a legitimate model output and is kept as `tools/svgbench/reference/real_q2_skyground.svg`,
the regression case for the fix. The ladder was restarted from scratch after the fix passed a
backdrop-invariance test (same subject on plain / transparent / vertical-gradient /
horizontal-gradient / sky-over-ground backdrops must score identically).
