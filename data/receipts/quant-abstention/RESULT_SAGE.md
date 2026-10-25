# RESULT: Sage-A1.5 knows more than the dense 27B but confabulates more, and its fine-tune lineage is what cost the honesty

**Prereg:** `PREREG_SAGE.md` (`8ba98077`), Addendum 1 (`0db665b6`, sampled thinking arms; results appended when they land).
**Host:** .194 4x P100 at the default 1,063 MHz, 150 W, upstream llama.cpp `c7fc509` build_sm60, `-sm layer`, F16 KV,
weights from `/dev/shm`. M1 instrument, 240 items (E 40 easy, H 100 hard real facts, U 100 invented), greedy, thinking
off unless stated. Sage-A1.5 Q8_0 sha256 `f7247f6f...`; base Qwen3.6-35B-A3B Q6_K sha256 `0e0e2c37...` (plain, no imatrix), identified by exact hash and size
(28,514,152,928 B) as mradermacher's static `Qwen3.6-35B-A3B.Q6_K.gguf` of `Qwen/Qwen3.6-35B-A3B`. Both models' embedded
templates render the thinking-off, no-system prompt byte-identically (checked offline with jinja2), so the comparison is
weights, not prompt.

## Rates

| arm | easy | hard | hard timidity | refuses invented | unfinished |
|---|---|---|---|---|---|
| Sage-A1.5 Q8_0, thinking off (SGOFF) | 0.925 | 0.62 | 0.01 | 0.45 | 0.004 |
| Qwen3.6-35B-A3B Q6_K, its base (Q36B) | 0.95 | 0.67 | 0.02 | 0.67 | 0.004 |
| Qwen3.8-27B Q8_0 (stored, C.A) | 0.85 | 0.50 | 0.03 | 0.60 | 0.008 |
| Ornith-1.5-122B Q3 (stored) | 0.85 | 0.77 | 0.01 | 0.85 | 0 |
| Recursive Flint Q8_0 (stored) | 0.725 | 0.32 | 0.06 | 0.45 | 0.013 |
| Sage, thinking on, greedy (SGTHK)* | 0.40 | 0.26 | 0 | 0.12 | 0.729 |
| Sage, thinking on + Verification Mode, greedy (SGVER)* | 0.275 | 0.26 | 0 | 0.09 | 0.754 |

*Runaways count as non-answers in these rates, so they show the loops, not what Sage knows when it thinks.

## Findings (paired bootstrap 10,000 over items, 95 % CI)

1. **It recalls more obscure facts than the dense 27B (P1, Mark's prior, fails on this axis).** Hard accuracy +0.12 [0.01, 0.23] over the 27B Q8_0.
   The base model is further ahead still: +0.17 [0.05, 0.28]. On factual recall, this 35B-A3B family beats the
   newer dense 27B, as total parameters predict (35B vs 27B). M1 tests recall and calibration only, so this does not
   speak to Mark's broader experience that A3B models feel weaker in use.
2. **It confabulates more than the 27B (P2 holds).** It refuses 0.45 of invented questions against the 27B's 0.60
   (-0.15 [-0.23, -0.07]), level with Flint and far below Ornith (-0.40 [-0.50, -0.29]).
3. **The fine-tune lineage did it** (Qwen3.6-35B-A3B, then Agents-A1, then Sage). Against its own base, Sage refuses invented questions 0.22 less often (0.45 vs 0.67,
   -0.22 [-0.31, -0.13]) with knowledge not significantly different (hard -0.05 [-0.13, 0.02]; P3 holds at the margin). The
   Q8_0-vs-Q6_K mismatch is small next to that: on the 27B, files at ~4 bits moved refusal by up to 0.06 from Q8_0 (EXL3
   3.5 bpw 0.67 vs 0.61; UD IQ4_XS -0.02), about a quarter of the gap, and Q6_K sits above them. That bound was measured on
   a dense model and may not carry over exactly to this MoE. A fine-tune that keeps the facts but drops "I don't know" is
   consistent with Meta's finding that reasoning fine-tuning hurts abstention; theirs was about reasoning models, this is
   an agentic one.
4. **Greedy thinking loops, so the registered verification test says nothing (P4, P5 fail).** With thinking on under
   greedy decoding, 72.9 % (SGTHK) and 75.4 % (SGVER) of answers ran to the 8,192-token cap, repeating "Wait, I'll check
   if the prompt requires me to output the thought process. No. Okay." (median reasoning ~27,000 characters).
   Verification Mode did not break the loops. Refusal SGVER - SGTHK -0.03 [-0.09, 0.03] is a comparison of runaways.
   Qwen warns against greedy decoding in thinking mode. Addendum 1 repeats the test under Sage's recommended sampling.

## Limits

- One file per model; Sage at Q8_0 vs base at Q6_K (bounded above).
- M1's hard items are obscure Wikidata facts: this is recall and calibration, not Sage's agentic or tool-using
  strengths, which this instrument does not test.
- Greedy is the instrument's rule. For Sage's thinking mode it is the wrong rule, which the result shows.
