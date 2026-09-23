# Pre-registration — does MTP change multi-turn agent OUTCOMES, or only the text?

**2026-09-23, written during the 3-item smoke (plumbing and timing only), before any arm of the
full run.** RX 9070 XT, buun `38ada0e1b` `build_rocm`, runner `argus/run_mtp_agentic.sh`.

## Question

Speculative decoding should not change the output distribution, but in practice it is not
bit-exact. Creative-writing users complain about MTP. For agents, the question that decides
deployment advice is: **when MTP changes an agent's trajectory, does it change it for the WORSE
more often than for the better?** MTP here is ~2x decode (27.6 -> 55.8 t/s, 82 % acceptance in the
smoke), so nobody will give it up unless harm is shown.

**Prior art checked:** `ledger_precheck.py "MTP speculative decoding agentic tool calling errors
output quality" --deep` -> found:
- `battle16gb/MTP_STRUCTURED_OUTPUT.md` (07-29): single-turn, n=6 draws, one model. Prose
  drifts, tool calls stable and correct in both arms, and code differed semantically once.
- `spec-decode-determinism/RESULT_SPECULATION_IS_NOT_BIT_EXACT.md`: speculation never
  reproduces non-speculative output.
- `mtp-transfer/RESULT_MTP_HEAD_TRANSFER.md`: the drafter does not change output; the
  speculative path does.
- INDEX L222: a fixed wall-clock timeout converts decode speed into apparent capability.

**What this adds:** multi-turn agent **outcomes** (40 argus scenarios, programmatic verdicts),
three seeds per arm, compared on the **direction** of disagreements, not just their rate. Plus
an equivalence bound, so that "no harm found" is a claim with a size.

## Fixed setup (both arms)

- Model `Qwen3.8-27B-UD-IQ3_XXS.gguf` (unsloth, stock), sha256
  `0a6129dcbbbe72f423dc67e0e3bbfbbdf3e923981a3637687ebb96a46c59d6be`, native MTP head
  (`qwen35.nextn_predict_layers = 1`).
- Server: `-c 65536 -np 1 -fa on -ctk turbo4 -ctv turbo4 --no-cache-prompt -b 2048 -ub 512 --jinja`,
  Qwen card sampling `--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repeat-penalty 1.0
  --presence-penalty 0`, `--chat-template-kwargs {"reasoning_effort":"medium"}` (argus convention;
  unset is silently xhigh, AFM-23), port 8091.
  - **Static turbo4 KV, not VBR.** The drafter changes free VRAM, so a VBR schedule would differ
    between arms.
  - `--no-cache-prompt`: warm cache + speculation is bistable.
- The only difference between arms: `--spec-type draft-mtp --spec-draft-n-max 2`.
- Each arm: a fresh server, `/props` asserted (model, temp, top_k, seed), one warmup discarded,
  and `bool(draft_n) == arm is MTP` asserted.
- Harness: argus driver, corpus `argus/families_v4.json` (40 items, 9 families), bwrap-sandboxed
  agent (AFM-45), deny rules (AFM-44), fixture `mtpag` built by `make_fixture.sh`, SOUL sha
  `36c1f5a2` (as the 9B gate). **A pristine agent-home is restored before every item**, so
  Hermes memory and caches cannot carry over between items or arms.
- **Calendar pinned:** `TZ=Etc/GMT+12` and `HERMES_TIMEZONE=Etc/GMT+12`, so the agent's date is
  constant across the whole run. The runner aborts if it rolls over.
- Chat-template dialect check (AFM-41): **PASS** on this GGUF's template.

## Arms and order

`OFF-s1, MTP-s1, OFF-s2, MTP-s2, OFF-s3, MTP-s3` (seed = `--seed`), alternating so drift over
the night cannot line up with an arm. 40 items each, 240 rows.

## Scoring

- Pass per item as in `tools/argus_reps_compare.py` (`CORRECT`, or `CLARIFIED` for
  `no_action_ask`).
- **Timeouts are FAILURES, not voids.** The driver labels a timeout `INFRA` (TimeoutError). Both
  existing void rules would drop exactly the rows the slower arm loses, so any `INFRA` row whose
  `why` contains `TimeoutError` is recoded as a failure before analysis. Timeouts are reported per
  arm. The per-item limit is set from the smoke to well above either arm's need.
- Other voids: the **judge rule** (INFRA/TOOL-FAIL) is primary, as in the 9B gate; the noise-floor
  rule is reported alongside. An item-seed pair is dropped only if either side is void.

## Primary analysis

- **Unit = item** (40), not item x seed: seeds are clustered within items.
- For each item, `d_i = pass-rate(MTP) - pass-rate(OFF)` over its non-void seeds.
- Report mean `d` with an item-level 95 % CI (t over items) and an **exact sign-flip permutation p**
  over items.
- **Equivalence (the deployment question):** a TOST at margin **±10 pp** (90 % CI of mean `d`
  inside [-10, +10] pp) => "MTP does not change agent outcomes by more than 10 pp on this model".

| outcome | reading |
|---|---|
| CI inside ±10 pp | **equivalent**: keep the 2x |
| mean `d` < 0 with p < 0.05 | **MTP harms agents** here |
| mean `d` > 0 with p < 0.05 | MTP helps (would itself need explaining) |
| neither | **inconclusive**; the report states the CI and does NOT say "no effect" |

**Predictions** (confidence): equivalent within ±10 pp, **0.60**; harm detected, **0.10**.

**Sizing, stated in advance:** at a per-seed discordance near argus's ~12 % floor, per-item `d`
has an SD of roughly 0.2-0.3, so the SE over 40 items is ~0.04, a 90 % CI half-width of ~7 pp, and
an MDE (80 % power, two-sided α = .05) of ~11-13 pp. Harm smaller than that cannot be
distinguished from zero with 40 items.

## Secondary (descriptive, not tested)

- **Perturbation control, in-run:** within-arm discordance (OFF-s_a vs OFF-s_b, MTP-s_a vs MTP-s_b)
  vs between-arm discordance, via `argus_reps_compare.py`. This replaces the separate `-ub`
  control arm discussed with Mark, since seed-to-seed variation is already a perturbation of
  known character.
- **Structural:** `tool_call_leak` count, tool-call parse failures and the `TOOL-FAIL` share per
  arm. This is the failure MTP could plausibly cause directly.
- Per-arm timeouts, `secs` per item, total tokens, draft acceptance from the server logs.
- Determinism: the smoke runs OFF-s1 twice on 3 items. Whether a seed reproduces the same
  trajectory is recorded before the full run. It changes only the wording of the within-arm
  analysis (fixed vs independent draws), not the primary test.

## Not established whatever the outcome

One model and quant, one card, one harness (Hermes via ACP), one corpus. `n-max 2` only. Card
sampling at temp 0.6; greedy agents may differ.
