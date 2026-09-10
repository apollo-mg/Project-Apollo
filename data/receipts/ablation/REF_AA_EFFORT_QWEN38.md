# Reference: Artificial Analysis, Qwen3.8-27B xhigh vs medium

**Captured 2026-08-26** from `artificialanalysis.ai` charts (screenshots). Recorded here
because AA publishes bar charts, not tables — the underlying data is not freely downloadable,
and the page text does not carry per-benchmark numbers (verified by fetch: only the headline
index, token count and cost extract).

## The 7 of 9 evaluations we could capture

| evaluation | xhigh | medium | delta |
|---|---:|---:|---:|
| **AA-Omniscience** (non-hallucination) | 70% | **33%** | **−37** |
| Humanity's Last Exam | 34% | 14% | −20 |
| **Terminal-Bench v2.1** (agentic) | 80% | **65%** | **−15** |
| *Intelligence Index v4.1.1* | *52* | *44* | *−8* |
| SciCode | 45% | 38% | −7 |
| GPQA Diamond | 91% | 85% | −6 |
| AA-LCR (long-context reasoning) | 77% | 76% | −1 |

**Not captured:** GDPval-AA v2, τ³-Banking, CritPt.

**xhigh cost, from the page:** 160M output tokens across the index, $0.37 per task,
51.8 tok/s. No medium equivalent published — which is the number that would settle the
cost-vs-quality trade at benchmark scale.

## The pattern in the deltas

Sorted, the gap is **largest on hallucination and hard reasoning, smallest on retrieval**:

```
AA-Omniscience -37 | HLE -20 | Terminal-Bench -15 | SciCode -7 | GPQA -6 | AA-LCR -1
```

AA-LCR is essentially unaffected (−1). Long-context *retrieval* does not benefit from extra
deliberation; deciding whether you actually know something does. That is coherent with AFM-23,
where the effort string's effect was **conditional on unresolvability** — it changes behaviour
when there is something to deliberate about and does nothing when there is not.

## Our own check disagrees on the one we can test

`effort_cal_medium.jsonl` (tier_cal, 3 seeds × 16 items, card sampling temp 1.0, Q6_K on
sm_60): **medium non-hallucination = 88%** (3 confabulations / 24 unanswerable), 23/24
answerable correct, **zero NO-STOP**.

88% against AA's 33% for the same setting on the same model. Almost certainly **corpus
difficulty**, not a contradiction: AA-Omniscience is built to elicit hallucination on obscure
factual claims; `tier_cal`'s 8 unanswerable items are authored to be plainly unknowable. Ours
is the easier abstention task.

**The consequence is that AA's number cannot be read as a property of the model alone.** A
non-hallucination rate is a property of (model, effort, corpus difficulty), and 88% vs 33%
is how wide that spread gets. Anyone using "medium hallucinates 67% of the time" as a
deployment input is importing AA's corpus difficulty along with it.

## Where we are entitled to a claim, and where we are not

- **Entitled:** on our corpus, medium confabulates 3/24 and always terminates.
- **Not entitled:** that AA's number is wrong, or that medium is safe generally.
- **Open:** whether xhigh trades confabulation for non-termination. Early xhigh data has
  1 NO-STOP in the first 3 unanswerable items — the AFM-23 failure mode reproducing at card
  sampling. If it holds, the two settings **fail differently** rather than one dominating,
  and a single non-hallucination percentage cannot express that.
