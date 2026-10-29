# RESULT: Nanbeige4.3-33B knows the least of any model on M1 and confabulates freely, with or without thinking

**Prereg:** `PREREG_NANBEIGE.md` (`fd60e926`). **Model:** bartowski `Nanbeige_Nanbeige4.3-33B-Q8_0.gguf` (sha256
`8523452a...`, verified on both hosts). GGUF settings match the HF config (rope base 1.2e8, RMS eps 1e-5, no rope scaling,
SPM tokenizer), and the answers are fluent and well-formed, so this is the model, not a broken conversion. **Host:** .194
4x P100, default 1,063 MHz, 150 W, llama.cpp `c7fc509`, `-sm layer`, F16 KV. N33THK was interrupted at 180/240 when the
desktop session logged out (2026-10-26 03:59), and resumed on a fresh server per the stop rule (`nanbeige_resume.sh`).

| arm | easy | hard | hard timidity | refuses invented | unfinished |
|---|---|---|---|---|---|
| Nanbeige4.3-33B, thinking off, greedy (N33OFF) | 0.575 | 0.12 | 0.02 | 0.35 | 0 |
| Nanbeige4.3-33B, thinking on, T 0.6 (N33THK) | 0.50 | 0.14 | 0.01 | 0.26 | 0.054 |
| Qwen3.8-27B Q8_0 (stored, C.A) | 0.85 | 0.50 | 0.03 | 0.60 | 0.008 |
| Sage-A1.5 thinking off (SGOFF) | 0.925 | 0.62 | 0.01 | 0.45 | 0.004 |
| Qwen3.6-35B-A3B base (Q36B) | 0.95 | 0.67 | 0.02 | 0.67 | 0.004 |
| Recursive Flint (stored) | 0.725 | 0.32 | 0.06 | 0.45 | 0.013 |

1. **It recalls far less than the 27B (P1 fails, the other way).** Hard accuracy -0.38 [-0.48, -0.28]; easy -0.275.
   0.12 on hard items is the lowest of any model on this instrument (Flint 0.32, Bolt 0.41). The wrong answers are
   fluent confabulations: "The capital of Manica Province ... is the city of Maputo", a province's own name given as its
   capital, Daegu for North Gyeongsang.
2. **It refuses invented questions less than the 27B (P2 holds):** 0.35 vs 0.60, -0.25 [-0.35, -0.15]. Only Bolt
   (0.16) is lower on M1.
3. **Thinking does not help (reported).** Hard +0.02 [-0.02, +0.06]; refusal of invented items -0.09 [-0.18, 0.00].
   11 invented-item answers ran to the 8,192 cap, most still searching ("I can try to recall from SPARQL examples");
   only 2 of their reasoning tails conclude unknown, and no answers are bare `UNKNOWN`, so the grader blind spot does
   not change this. P3 fails narrowly (unfinished 5.4 %).

**What it means.** Nanbeige's card benchmarks agentic coding, office work and reasoning, where it is level with or
ahead of the 27B; none of those test recall without tools. On M1 it is a skills-heavy, knowledge-light model: asked
cold, it fills gaps with fluent guesses. It is the opposite of Sage, which recalls more than the 27B and becomes honest
when it thinks.

**Limits:** one file; M1 is long-tail Wikidata recall and calibration (no tools); one sample per item in the thinking
arm.

**Note added 2026-10-29: two samplers came from the engine, not the vendor.** The request set only temperature 0.6 and top_p 0.95. llama.cpp filled the
rest with its defaults, top_k 40 and min_p 0.05 (recorded in the run's header `props`). The model card's published config sets neither.
So this arm is the vendor's settings plus llama.cpp's cut-offs, not the vendor's settings alone. New recipes set top_k and min_p
explicitly, and `abstend.py` warns when a sampled mode leaves them to the engine.
