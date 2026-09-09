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
