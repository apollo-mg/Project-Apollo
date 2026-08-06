# Pastable for JabbaTheDuck — Blackwell fork fidelity check

Context: he posted a llama-bench table for a Blackwell-only llama.cpp fork ("Blackbeard",
`8ba2152` vs upstream `e9fa078`), RTX 5090, Qwen3-Coder-30B-A3B Q4_K_XL, `-ngl 99 -t 24`:
pp128 +175%, pp512 +135%, pp1024 +125%, tg128/tg256 +3%. Says he stripped everything but
CPU+CUDA and won't upstream it.

Framing per Mark: lead with what our own recent testing documented — innocent-looking changes
breaking determinism — not with "you're probably wrong." All figures below are checked against
receipts in this repo; citations at the bottom.

---

## MESSAGE 1

Those numbers hold together, for what it's worth. Your speedup *shrinks* as batch grows —
2.75× at pp128, 2.35× at pp512, 2.25× at pp1024. If the win were better tensor-core math
you'd expect it flat or growing, since big GEMMs are where math throughput dominates. Biggest
gain at the smallest batch is the signature of fixed per-call overhead coming out: kernel
launches, backend dispatch indirection, graph re-capture. On a 30B-A3B MoE with a swarm of
tiny per-expert GEMMs that's exactly where the fat is, and tg being +3% fits too since tg is
bandwidth-bound and there's nothing there to strip. So the shape of your table matches the
story you're telling about it.

Reason I'm bringing this up at all: we've spent the last week finding that innocuous-looking
changes break temp-0 determinism, and we've got receipts on three separate ones now.

1. **MTP speculative decoding** (Qwen3.6-35B-A3B on turboquant). The acceptance logic is
   *provably correct* — read it, `result.push_back(id)` always pushes the target model's
   token, the draft is only a comparison key. Zero steps in the acceptance path are wrong.
   Base build at temp 0: **1 distinct output across 6 draws**. Same build with MTP on:
   **4 distinct outputs across 6 draws**, and unstable *within a single server instance*, not
   just across restarts. Mechanism is batched verification changing float reduction order,
   which flips near-tied argmaxes. We measured the flip margin: **0.03125**, tighter than
   99.25% of token positions. On an agent benchmark that became **35% of scenarios unstable**
   — more than double the ~15% flip floor we measured for deliberately *randomised* sampling.
   And the majority vote scored identically to base (14/20), so running it once per config
   would have shown nothing at all.

2. **turbo4 KV codec on RDNA4.** Found by accident while chasing a *speed* question. ~9% NaN
   rate, perplexity spread 8.0984–8.1825 across supposedly identical runs. Nobody was looking,
   because a cache format isn't a math change.

3. **Pascal sm_60 FAST_FP16.** A compile-time gate that had been on for years and never
   measured. Median KLD vs an fp32 truth base **0.002298**, top-token agreement **96.53%** —
   roughly 1 in 29 next-token predictions changing outright. Three-line patch took it to
   **0.000001 / 99.89%** at **zero** speed cost.

## MESSAGE 2

Where your fork sits in that: overhead removal is usually numerically *identical*, which is
the good case. But if anything got fused or retiled along the way, reduction order changed,
and that's case 1 above. The thing is `llama-bench` structurally cannot see it — it measures
throughput and never inspects a token it produced. Your table has no fidelity axis, not
because you skipped it, but because that tool doesn't have one.

**Don't use perplexity to check this.** We've got a receipt where PPL inverts the ordering
outright: same five runs, same base, and Q3_K_M has the *worst* same-top (90.6%) and *worst*
median KLD (0.0184) while posting the **best perplexity in the whole ladder** — better than
Q8, better than the BF16 weights it was quantized from. PPL only scores the true token and
lets errors elsewhere in the distribution cancel out.

KLD is the instrument. ~20 min, upstream flags, no extra tooling:

```bash
# 1. Truth base from UPSTREAM, same model file
llama-perplexity -m Qwen3-Coder-30B-A3B-Q4_K_XL.gguf \
  -f wiki.test.raw -c 2048 --chunks 32 \
  -ctk f32 -ctv f32 -fa off -ngl 99 -ub 128 \
  --kl-divergence-base upstream_truth.kld

# 2. Score YOUR FORK against it — identical flags, plus --kl-divergence
llama-perplexity -m Qwen3-Coder-30B-A3B-Q4_K_XL.gguf \
  -f wiki.test.raw -c 2048 --chunks 32 \
  -ctk f32 -ctv f32 -fa off -ngl 99 -ub 128 \
  --kl-divergence --kl-divergence-base upstream_truth.kld
```

f32 KV and `-fa off` on purpose — you want the only difference between the two runs to be
your kernels, not the cache codec or the attention path.

**Pass:** median KLD ~1e-6 and top-token agreement ≥99.9%. That's the "same model, just
faster" signature; our Pascal patch landed exactly there. **Fail:** anything in the 1e-3 range
with same-top down in the 96–98% band means the fork is computing a materially different
model, and 2.25× becomes a tradeoff you'd want to state rather than free speed.

Cheaper 5-minute smoke test if you want a signal first: serve it, temp 0, same prompt, hash
the output, **2 draws per instance across 3 restarts**. A healthy build gives 1 distinct hash
out of 6. More than 1 and you've got reduction-order nondeterminism, and the KLD run tells you
how big. Do it as 2×3 and not 6 draws on one instance — we made exactly that mistake, and a
single-instance run showed 3/3 identical for a config that turned out to be unstable.

If it comes back clean you get a much stronger claim than the bench table alone supports:
*2.25× prefill, bit-comparable output.* That's the version people can actually act on. And
prefill is the right thing to have optimised — agent loops re-ingest long context every turn,
so 2.25× there beats 2× on tg for real workloads.

---

## Provenance for every number above

| claim | receipt |
|---|---|
| speedup ratios 2.75/2.35/2.25× | arithmetic on his own posted table (internally consistent) |
| base 1/6 distinct, MTP 4/6 distinct, unstable within instance | `battle16gb/MTP_DETERMINISM.md` |
| flip margin 0.03125, 99.25th pct; 35% scenario instability; 14/20 both arms; ~15% sampling flip floor | `battle16gb/MTP_HA20_AND_MARGIN.md` |
| acceptance rule is correct (`common/sampling.cpp:621`) | `battle16gb/MTP_HA20_AND_MARGIN.md` |
| turbo4 ~9% NaN, PPL 8.0984–8.1825 | `battle16gb/BUUN_RDNA4_PASTABLE.md` |
| sm_60 0.002298/96.53% → 0.000001/99.89%, zero speed cost | `Apollo Docs/gist_sm60_fast_fp16_DRAFT.md` |
| Q3_K_M PPL inversion (90.637% same-top, 0.018433 median KLD, best PPL) | `Apollo Docs/Instrument_Disagreement_PPL_vs_KLD.md` |
| KLD flag semantics (`--kl-divergence-base` writes without `--kl-divergence`, reads with it) | verified against `llama-perplexity --help` on `build/bin`, 2026-07-30 |
| command shape | `Apollo Docs/Lab_Spec_Puzzle75B_Eval_Campaign.md:80-90` |

Unverifiable by us: his fork's source. Everything above is a read of a posted bench table
plus our own measurements — stated as such in the message.
