# PREREG: does the pi adapter ruin Hermes? (2026-11-22, before any main-run item)

**Mark's question (11-21):** "I wonder if the adapter ruins the experience in Hermes." The pi adapter (harness-hub's
agent-RL LoRA for Qwen3.8-27B) was trained inside the pi coding agent; Hermes is a different harness and an assistant,
not a coding tool. argus measures exactly the assistant behaviours: act when a request is clear, ask when it is
ambiguous or cannot be satisfied, answer a question without acting -- scored from the fake world's audit log, not the
agent's own account.

**Prior art checked:** `ledger_precheck.py "pi adapter Hermes argus act ask clarify"` -> the adapter's own receipts
(`pi-adapter/RESULT_PI_ADAPTER.md`: thinking off, it declares impossible coding tasks far more often than its base,
no false alarms) and argus's (`argus-v5/RESULT_V5_VALIDATION.md`: 83 items, twin concordance 90 %, cluster by
template; `mtp-agentic/RESULT_MTP_AGENTIC.md`: the paired-arm design). Never measured: the adapter in Hermes.
**What this adds:** that.

## Arms and settings

- **BASE:** Qwen3.8-27B Q8_0 (sha256 `a680f44a...`), .194 GPUs 0+1 (:8190). **PIA:** the same file + `--lora`
  `Qwen3.8-27B-pi-lora-F16.gguf` (`a64f9184...`), GPUs 2+3 (:8191). buun `0b2789f23` `build_sm60`.
- Both: `-c 65536 -ctk q8_0 -ctv q8_0 -np 1 -sm layer -fit off --jinja --temp 0 --seed 1`, thinking off
  (`--chat-template-kwargs {"enable_thinking":false}`); Hermes sends no sampling or thinking fields to a custom
  endpoint, so the server settings decide. 64K because this Hermes refuses smaller windows; q8_0 KV so 64K fits a
  two-P100 lane. Prompt cache at the server default (on): runs are single draws, the same condition for both arms.
- The agent: hermes-go at its current checkout, ACP transport, bwrap sandbox (`argus/sandboxed_agent.sh`), deny rules
  and loop hard-stop as every argus fixture; reached through an ssh tunnel (127.0.0.1:8091 / :8092). Preflight on the
  tunnel: model path, temperature 0, adapter count (0 / 1), n_ctx >= 64,000, thinking off, warm-up discarded.
- Fixtures `hbA`/`hbB` (BASE) and `hpA`/`hpB` (PIA), built by `argus/build_pi_fixtures.sh` on the run's UTC date
  (world anchored to the following Thursday, as argus does); a pristine agent-home restored before every item. The two
  arms run side by side. `argus/run_argus_pi.sh main`.

## Items and scoring

argus `families_v5.json`, all 83 items: 47 act, 30 ask (`no_action_ask`), 6 answer-without-acting (`no_action`), in
43 templates (40 with a world-B twin, 3 single). Pass as `tools/argus_reps_compare.py`: CORRECT for act and
no-action items, CLARIFIED for ask items. Voids: the judge rule (INFRA, TOOL-FAIL), except that a timeout (INFRA with
TimeoutError) is a FAILURE, as in the MTP run. A template's score is the mean pass over its non-void items; a pair is
dropped only if a side is void.

## Predictions (unit = template, 43 clusters; mean PIA - BASE, 95 % t-interval, exact sign-flip p)

- **H1 (the headline, equivalence):** overall, the adapter changes Hermes's pass rate by less than 10 points: the 90 %
  interval of the mean difference lies inside [-10, +10] pp. Readings: inside -> "does not ruin it"; mean < 0 with
  p < 0.05 -> "it hurts Hermes"; mean > 0 with p < 0.05 -> "it helps".
- **H2 (ask side):** on the ask templates, PIA passes LESS than BASE (mean difference < 0). Basis: it was trained where
  nobody answers questions and a bonus paid for fewer steps, so asking never paid. Confidence 0.6.
- **H3 (act side):** on the act templates, PIA passes no less than BASE minus 5 points. Confidence 0.5.
- Reported without prediction: the no-action items; per family; time and tool calls per item; timeouts; INFRA.

## Run and limits

Sized from the timing smoke (`smoke/`, home paths redacted; four items per arm, all passed on both: 210, 45, 60 and
60 seconds, about 95 s per item); 83 items per arm side by side, about 2.5 to 4 hours, inside one UTC day (the runner aborts on a rollover). .194 powered off at the end.
Limits stated now: one harness version, one seed, thinking off (the adapter's setting), greedy; an assistant corpus of
a fake mailbox and calendar; the adapter runs outside its training harness by design.
