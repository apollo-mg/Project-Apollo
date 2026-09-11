# Run notes — annotations made during the ladder (not protocol changes)

The pre-registered score is reported exactly as computed. These notes record, as each was found and
**before the remaining reps ran**, which results are instrument artifacts rather than properties of
the drawing. Per the commitment made before rep 2, the scorer is **not** changed mid-run; affected reps
are annotated, not excluded.

## Q2_K_XL rep 2 — p1 9/10: artifact (grass-ellipse tips)

See the prereg's "Known false positive" section. The two `assembly_coherent` near fragments (114 and
113 cells, bottom corners) are the curved tips of a grass ellipse whose columns end in sky. All four
revisions scored 9/10 on the same artifact; none touched the grass, so it **cancels within the pair**.
The corrections did find real faults the scorer cannot see: *"Near leg dangles in mid-air — its foot
hovers at (173, 201) with no pedal beneath it; only one pedal is drawn."*

## IQ2_M rep 2 — p1 6/10: artifact, all four failures

Visually a sound pelican on a bicycle. Failing `two_lower_clusters`, `clusters_separated`,
`structure_between`, `assembly_coherent` — none a real defect:

- **Wheel checks:** the lower-band column profile is one continuous run, x = 72–420 (profile max
  0.491, threshold 0.123). A grey shadow ellipse under the bike — not touching the canvas edges, so
  counted as ink — plus the chainstay and down tube keep every column between the wheels above
  threshold. All three wheel checks derive from that single run.
- **`assembly_coherent`:** two near fragments. The **wing** (162 cells) is isolated because the body's
  white fill is indistinguishable from the white backdrop, leaving the wing as an island inside the
  outline. The **head** (181 cells) is cut off because the thin diagonal neck breaks apart under
  4-connectivity at 4× downsampling (its pieces are components of 10 and 7 cells).
- **All three corrections scored 6/10 on the same four failures.** `goal3` (13,660 tokens) diagnosed
  *"No wings/arms on the handlebars — the pelican is just sitting on the bike; nothing reaches forward
  to grip the bars, so it doesn't read as 'riding'"* and **added a wing reaching forward with a hand on
  the grip** — a real semantic fix, invisible to the score. (IQ4_XS rep 1's intent correction made the
  same kind of fix unprompted.)

## Running tally, recorded before rep 3

Non-ceiling first drawings so far: **2 — and both are non-ceiling purely because of instrument
artifacts.** P-L1 and P-L4 are computed only on non-ceiling reps, so they are currently being computed
entirely on artifact-driven reps. **The final report will print the arithmetic verdicts as
pre-registered, and state beside them how many of the reps underneath are artifact-driven.** If all of
them are, the verdicts carry no information about feedback utilization, and the report will say so.

## IQ4_XS rep 2 — p1 9/10: REAL — the first non-artifact, non-ceiling rep

Backdrop pure white (255,255,255). The neck is
`<path d="M292 142 Q 332 122 348 82" stroke="#ffffff" stroke-width="24" …>` — **a white stroke on a
white canvas, invisible in the render.** The head (189 cells) genuinely floats with no visible
connection to the body; the scorer's `assembly_coherent` failure matches what a viewer sees.

- **`intent2` → 10/10.** Diagnosed *"Neck has no outline — it's drawn as a plain white stroke with no
  border, so it looks like a floating white tube rather than a defined neck"* and gave it a border
  (white stroke 24 → 23 over a darker outline). The neck becomes visible and joins head to body:
  **3 components → 1.**
- **`goal2` and `goal3` → 9/10.** Both pursued other faults (*"Legs too thin / unclear — the feet don't
  visually 'grip' the pedals"*) and never addressed the invisible neck.
- **Framing effect −1: intent beat goal**, the opposite of P-L1's predicted direction. One clean data
  point.

## Rule used to call a failure real or artifact (stated so it can be checked)

A failed check is **real** if the element responsible is *not visible in the render* — e.g. drawn in
the backdrop colour — so a viewer sees the same fault the scorer reports. It is an **artifact** if the
element *is* visible and the scorer mis-segments it: grass-ellipse tips counted as ink; a visible grey
neck broken apart by 4-connectivity; a wing inside a visibly outlined body. Applied so far:
Q2_K_XL r2 artifact, IQ2_M r2 artifact, IQ4_XS r2 real. **This is still my judgement from looking at
renders, and is disclosed as such**; the colour test (element colour vs backdrop colour) is the part
anyone can re-check from the saved SVGs.

## Tally, updated before the remainder of rep 3

Non-ceiling first drawings: **3 — two artifact-driven (framing effect 0, 0), one real (effect −1).**
