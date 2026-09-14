# One-line repro — `assembly_coherent` fails a drawing because it has a sun in the sky

**`svg_probe.py`, unchanged, 64×30.** Files in this directory.

```
$ svg_probe.py m_rep2_p1.svg  --cols 64 --rows 30
   9/10   fails: assembly_coherent    component_sizes [2951, 174]   near_fragments [174]

$ svg_probe.py m_rep2_nosun.svg --cols 64 --rows 30
  10/10   fails: none                 component_sizes [2951]        near_fragments []
```

`m_rep2_nosun.svg` is `m_rep2_p1.svg` with exactly one element deleted and **nothing else changed**:

```xml
<circle cx="350" cy="45" r="22" fill="#ffd94d"/>
```

## Why

`assembly_coherent` is `not frags`, where a component counts as a fragment if it is **≥ `FRAG_MIN` × the
size of the main component** and lies near it (`svg_probe.py:215-217`). The threshold is **relative to the
main component**, so:

- A drawing that fragments into many pieces has a **small** main component, every other piece is small
  relative to it, and nothing trips the check.
- A drawing whose pelican is properly joined to its bicycle has a **large** main component (here 94.4% of
  ink), and now an ordinary decorative sun at 5.6% clears the relative threshold and fails it.

**Thinking-off rep 1 also has a sun and scores 10/10** — it has 13 components and `largest_component_frac`
0.634, so the sun never clears the bar. **The same sun passes in a fragmented drawing and fails in a
well-assembled one.**

## What it means

**The check does not measure what its name says.** It is intended to catch a detached body part — a wheel
off the frame, a head off the neck. On this drawing it catches the sky.

**And the penalty is conditional on drawing well.** A model is punished for a sky ornament only once it has
produced a properly connected bicycle, so the defect selects against exactly the drawings the benchmark
wants to reward.

**For v2:** any candidate scorer should be run against this pair first. `m_rep2_p1.svg` must not score below
`m_rep2_nosun.svg` — they differ by one decorative circle. It is a cheaper, sharper regression test than the
revision pairs in `NOTE_SVGBENCH_SCORER_COUNTEREXAMPLE.md`, and it takes a second to run.

Related: V2_NOTES.md item 1 (backdrop shapes that don't touch the canvas edge count as ink) is the same
family — decorative content entering structural checks.
