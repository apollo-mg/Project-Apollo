# Mark's prediction, logged 2026-09-19 12:42 EDT

> "The new floor feels around 3-bits to me now instead of 4."

## Timing, stated plainly

Logged **after** four of the seven cells had produced numbers, and Mark flagged it as such
himself: *"My prediction for the record. Late, but my prerogative."* It is therefore **not a
preregistration** and is not scored alongside P-L0..P-L5. Recording it this way is the point: a
prediction with its knowledge-state attached is still evidence, a prediction whose timing is
fudged is not.

**What was known to him when he said it:**

| cell | scored bpw | mean KLD | same-top |
|---|---:|---:|---:|
| G-IQ2XS | 2.476 | 0.202243 | 81.471% |
| A-IQ2XS | 2.822 | 0.174453 | 81.735% |
| G-IQ3XXS | 2.968 | 0.101180 | 86.549% |
| A-IQ3XXS | 3.465 | 0.073686 | 88.529% |

**What was NOT known:** A-IQ3S, and all three prism cells (C-XBIN, B-PTQ1, B-PQ2). So the claim
was made with both ternary cells still unmeasured -- the ones that bear most directly on where a
floor sits.

## Making it testable

"The floor" is not self-defining, and the ladder's own data says it is **not a knee**: KLD decays
smoothly and exponentially (`KLD ~ A*exp(-1.37*bpw)`, lambda within 5% across both scalar
families), so there is no elbow in the curve to point at. Any floor claim is therefore a
**threshold crossing**, and the threshold has to come from somewhere outside this panel.

The reading that makes the claim substantive: **"the floor moved from 4 bits to 3" is a statement
about codec progress, not about absolute quality.** It says a modern 3-bit quant now delivers what
a 4-bit quant delivered when the 4-bit rule of thumb was formed. That is checkable against the
EXL3 campaign's existing Q4-class measurements, which used this same `ref.kld`, this same corpus
and this same binary -- the comparison is already apples-to-apples and costs no GPU time.

Scored in `RESULT_LADDER.md` when the panel completes, against that definition, and reported
whichever way it lands.

---

# Scored, 2026-09-19 12:50 -- FALSIFIED on fidelity, UNSETTLED on usability

Scored against the EXL3 campaign's own 4-bit-class arms, which used **the same `ref.kld`, the same
`wiki.test.raw`, the same `buun-sm60-qual` binary and the same 40-chunk flags**. No new GPU time;
the comparison was already apples-to-apples.

## The direct comparison (no model, no extrapolation)

| arm | bpw | mean KLD | same-top |
|---|---:|---:|---:|
| **G-IQ3XXS** (modern 3-bit, GSQ-RCO) | 2.97 scored | **0.101180** | **86.549%** |
| EXL3 4.00bpw | 5.33 raw | 0.012002 | 95.431% |
| UD-IQ4_XS | 4.50 raw | 0.015727 | 94.245% |
| UD-Q4_K_M | 5.20 raw | 0.007840 | 96.225% |

A current 3-bit quant sits at **6.4x the KLD of UD-IQ4_XS** and **7.70 pp lower top-1 agreement**.
Against Q4_K_M it is 12.9x. **On fidelity, 3 bits is not the new 4 bits.**

Extrapolating GSQ's curve, matching UD-IQ4_XS would take about **4.29 scored bpw** -- roughly
UD-IQ4_XS's own size, i.e. no floor movement at all. **That figure is a 1.32 bpw extrapolation
from a 0.49 bpw measurement base and is not trusted**; it is recorded as an indication, not a
result. The 6.4x direct comparison carries the verdict.

(The reference arms' bpw are raw disk figures; their MTP heads were not subtracted because those
files were not re-measured. Correcting for a ~0.3 GB head moves them by about 0.1 bpw and changes
no conclusion.)

## Why "unsettled on usability" is not a hedge

**KLD over wikitext does not measure what "the floor" colloquially means.** This same project has
now documented the gap twice:

- `humaneval-plus/` found the Puzzle-75B vs Laguna gap was a **stopping-rule failure, not an
  answering failure**.
- `EXTERNAL_OBSERVATION_2026-09-19.md` logs three independent reports of Bonsai 2 failing at
  agentic work -- planning without emitting, deleting its own files, declaring "verified" falsely
  -- none of which a next-token distribution distance over wikitext is built to detect.

If the claim is *"3-bit models now hold together on real work where they used to fall apart"*,
this panel cannot falsify it. It can only say the distributions remain clearly further from the
reference than 4-bit's were. **Falsified on the metric measured; untested on the metric meant.**

Settling the intended claim needs a task panel (pass rate, tool-call validity, stopping
behaviour), not a fidelity ladder. Worth doing, and worth not pretending this ladder did it.
