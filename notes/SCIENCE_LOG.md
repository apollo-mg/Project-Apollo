# Science Log

Discoveries worth remembering, recorded when they happened, with the claim checked against the
primary source rather than the coverage. Kept so that if one of these ever turns out to matter
practically, we can look back at what was actually known on the day.

---

## 2026-09-08 — X(2370): the strongest case yet for a glueball

**A particle made of force, with no matter in it.**

### Why it can exist at all

Electromagnetism has no equivalent. Photons are electrically neutral, so light does not interact
with light. Gluons are different: they carry the colour charge they mediate, so they pull on each
other. That self-interaction means QCD predicts bound states made *only* of force carriers, with no
valence quarks anywhere inside. Predicted in the 1970s. Hunted ever since.

The hunt is hard for a specific reason: a glueball and an ordinary quark meson with the same quantum
numbers **mix**. You cannot simply find the particle — you have to show it is not a conventional
meson in disguise. That is why candidates like f₀(1500) and f₀(1710) were argued over for decades.

### What was actually established, and by which measurement

The claim rests on two *different* papers with very different error bars. Keeping them straight is
the whole point of this entry.

| | measurement | result |
|---|---|---|
| **2024** | Partial-wave analysis, J/ψ → γK⁰ₛK⁰ₛη′, on (10087 ± 44)×10⁶ J/ψ events | X(2370) observed at **>11.7σ**; spin-parity **0⁻⁺ determined for the first time**. Mass 2395 ± 11(stat) ⁻⁹⁴⁺²⁶(syst) MeV/c²; width 188 ⁻¹⁷⁺¹⁸(stat) ⁻³³⁺¹²⁴(syst) MeV |
| **2026-07-22** | Search for X(2370) → K*(892)⁰K̄⁰ via J/ψ → γK⁰ₛK⁰ₛπ⁰ | **No evidence.** B < 2.7×10⁻⁶ at **90% CL** |

**The 11.7σ belongs to the state and its quantum numbers — not to the glueball identification.**
That distinction is easy to lose and matters enormously. 11.7σ is a fluctuation probability on the
order of 10⁻³¹; the signal is not in doubt. But the *flavour-singlet* discriminator — the property
that actually separates glueball from ordinary meson — is a **null result at 90% CL**. A non-singlet
state should decay to K*K̄; X(2370) does not, and that suppression is the singlet signature.

So: overwhelming significance on the object, a modest limit on the property that identifies it, and
lattice QCD supplying the prediction both are compared against. Discovered 2011; mass and quantum
numbers agree with the lattice prediction for the lightest pseudoscalar (0⁻⁺) glueball.

### What the collaboration actually wrote

> "A dominant component of the lightest 0⁻⁺ glueball is **essential for a natural and complete
> explanation** of the properties of the X(2370)" — and the evidence **"supports"** that it is the
> dominant constituent.

**"Supports."** Not "confirms," not "proves." Popular coverage of this reached "confirmed" and
"proves an entirely new form of matter exists." Those are stronger claims than the physicists made,
and the gap between them is exactly the gap this log exists to preserve. The honest statement is
*dominantly glueball*, because mixing is never fully excluded — only made implausible.

### Could this ever be useful?

Almost certainly not directly, and it is worth being honest about that rather than inventing a
motivation. A width of 188 MeV implies a lifetime around 10⁻²⁴ s. Nothing is ever going to be built
out of these.

The real payoff is indirect and larger: **this validates lattice QCD as a predictive instrument in
the strongly-coupled regime.** Lattice QCD predicted a mass and a set of quantum numbers for an
object nobody had ever seen, decades in advance, in the one regime where perturbation theory fails
completely — and the object turned up where it was supposed to be. That licenses trusting lattice
methods elsewhere: neutron-star equations of state, nuclear structure, and the precision Standard
Model predictions that beyond-Standard-Model searches are measured against.

If this entry ever gets revisited because something practical came of it, the chain will almost
certainly run through *"we could finally compute strongly-coupled systems we previously could not"* —
not through anyone holding a glueball.

### Footnote for our own work

The reason this got checked rather than filed: the popular summary said "confirmed" and "proves,"
the primary source said "supports." Same failure shape we spent 2026-09-08 chasing through our own
benchmarks — a real, well-measured number with an overstated verdict attached. `tg` really was 19.65.
The decode medians really were 32.9 and 33.3. The fit prover really could not place the model. All
true, all misread. A big sigma retires statistical doubt and touches systematic doubt not at all.

### Sources

- [Lightest 0⁻⁺ Glueball as Dominant Constituent of X(2370), BESIII (arXiv:2607.20366, 2026-07-22)](https://arxiv.org/abs/2607.20366)
- [Observation of X(2370) and search for X(2120) in J/ψ→γKK̄η′ (arXiv:1912.11253)](https://arxiv.org/pdf/1912.11253)
- [X(2370) emerges as glueball-dominated particle in collider experiments — phys.org, Aug 2026](https://phys.org/news/2026-08-x2370-emerges-glueball-dominated-particle.html)
- [On the Nature of X(2370) (arXiv:2609.01342)](https://arxiv.org/html/2609.01342)

---

## 2026-09-08 — OpenAI claims a Navier-Stokes proof (Millennium Prize problem)

**Announced 2026-09-08.** OpenAI says an unreleased internal model produced a proof for the
Navier-Stokes existence-and-smoothness problem, one of the seven Clay Millennium Prize problems.

### The precise claim

**Finite-time blowup**, not global regularity. The claim is that the equations admit solutions where a
fluid's velocity becomes **infinite at a point in finite time** — physically impossible, so the
equations are (in the reporting's phrasing) "fatally flawed" as a model of real fluids.

This is the *negative* resolution, and it counts: the Millennium problem asks for a proof of existence
and smoothness **or** a counterexample. It is also the direction Terence Tao's programme has pointed
at for a decade — he proved blowup for an *averaged* Navier-Stokes and proposed building a "fluid
computer" that could drive a real singularity.

### The detail that matters most: it was certified in Lean

Reported as **certified using the Lean proof assistant**. This is qualitatively different from a
natural-language proof, and different from almost every other AI capability claim: a Lean-checked
proof does not require trusting OpenAI, the model, or the press release. It either type-checks
against the axioms or it does not.

**But Lean closes one gap and not the other.** It verifies that *the stated theorem follows from the
axioms*. It does **not** verify that the stated theorem is the one you think it is. The standard
formalisation failure is proving a subtly different statement — a weakened hypothesis, a shifted
quantifier, a definition whose name suggests more than it means. A correct proof of the wrong
statement type-checks perfectly.

So the live review question is **not** "is the proof valid" — Lean answers that — but **"is the
formalised statement actually the Navier-Stokes Millennium Problem?"** That is a human judgement
about semantics resting on a mechanically correct artifact.

### Compute

Reported: ~10,000 agents in parallel over **88 hours**, after a simplified version fell to ~1,000
agents in ~50 hours.

### "Solved" is not "prize"

The Clay rules require publication in a refereed journal **plus roughly two years of general
acceptance** in the mathematical community. That clock has not started.

### The credit dispute is separate from correctness

Tristan Buckmaster alleges OpenAI moved on the proof after becoming aware that he and Levent Alpoge
were using a particular method. OpenAI's Sebastien Bubeck: *"We did not use their prompt or proofs to
prompt our models."* This bears on credit, not on whether the Lean proof checks. Both can be true at
once.

### Why this is logged here

Same reason as the glueball entry: the coverage and the claim are not the same object. If this turns
out to be historic, this is what was actually established on day one — a Lean-certified proof of a
blowup statement, with the statement's fidelity to the Millennium problem still a matter of human
review, and the prize clock not yet running.

### Sources

- [OpenAI claims blockbuster math breakthrough amid swirl of controversy — Scientific American](https://www.scientificamerican.com/article/openai-claims-blockbuster-math-breakthrough-amid-swirl-of-controversy/)
- [OpenAI claims huge maths breakthrough on a famed 'Millennium Problem' — Nature](https://www.nature.com/articles/d41586-026-02842-5)
- [OpenAI says AI solved one of math's hardest problems in days — BNN Bloomberg](https://www.bnnbloomberg.ca/business/artificial-intelligence/2026/09/08/openai-says-ai-solved-one-of-maths-hardest-problems-in-days/)
- [Ten advances in mathematics and theoretical computer science — OpenAI](https://openai.com/index/ten-advances-in-mathematics/)
