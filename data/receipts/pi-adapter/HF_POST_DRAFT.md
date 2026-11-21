Title: Independent results outside pi: honesty on made-up questions and on impossible tasks (thinking off and xhigh)

Thanks for releasing the adapter and documenting the training. We ran it against its own base on two of our
instruments, outside the pi harness, and the results are mostly very good news, so we wanted to share them.

Setup:
- Your GGUF adapter (Qwen3.8-27B-pi-lora-F16.gguf, revision e8c52527, sha256 checked) loaded with --lora on our own
  Qwen3.8-27B Q8_0, so the two arms differ only by the adapter. llama.cpp (buun fork) on Tesla P100s, greedy, prompt
  cache off.
- M1: 240 short questions built from Wikidata (40 easy, 100 hard but real, 100 about things that do not exist), with
  UNKNOWN offered as an answer. Thinking off.
- Agent test: our own small coding-agent harness (not pi), 30 tasks: 21 impossible as written (two tests that
  contradict each other, a test that contradicts the spec, required input data missing) and 9 solvable twins. The
  agent ends with finish(outcome = completed / impossible / not_completed). 30 steps, one reminder if it loops or
  reaches step 20.

Results, thinking off:
- M1: no change at all. Made-up questions answered UNKNOWN 60/100 for both; hard real questions 52 vs 50. The five
  other variants we have measured against their own base (SFT, distillation, an abliteration, a point release) all
  lowered the UNKNOWN rate, by 7 to 19 points. Yours is the first that did not.
- Agent: said "impossible" on 13/21 impossible tasks vs 4/21 for the base (11 of them before any reminder; paired 9
  vs 0, p = 0.004). Missing-input tasks 6/6 vs 0/6. Solvable twins 8/9 vs 6/9, with no false "impossible". No gamed
  checks, no false success claims, and every report named the actual cause. Median steps 13 vs 21.5.

Thinking on (reasoning_effort xhigh, earlier reasoning kept in the history), one seed, 7 impossible + 3 solvable:
- Base and adapter both said "impossible" on 7/7 and solved 3/3. So with thinking off, the adapter gets most of the
  way to base-with-thinking (5/7 on the same tasks, 4 of them unprompted) in less than half the time, which matches
  your card's efficiency claim on a different kind of task.

One edge case, in case it is useful: in an ablation (thinking off, but with the xhigh effort sentence injected into
the system prompt by hand) the adapter once wrote the missing input file itself to make the check pass, and said so
in its report. We have not seen that in any normal setting.

Write-ups, with the per-item records:
https://github.com/apollo-mg/Project-Apollo/blob/main/data/receipts/pi-adapter/RESULT_PI_ADAPTER.md
https://github.com/apollo-mg/Project-Apollo/blob/main/data/receipts/pi-thinking/RESULT_SEED2.md

Caveats: our harness, not pi; one quant (Q8_0); greedy decoding; small counts (21 impossible tasks on three task
templates); the thinking-on comparison is one seed.
