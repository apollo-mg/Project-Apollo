# Battle for 16GB — the agentic leg: Ternary-Bonsai-27B vs Gemma-4-12B QAT on HermesAgent-20

RX 9070 XT 16 GB (gfx1201), control plane 10.0.0.5. Date 2026-07-29.
Benchmark: stevibe's BenchLocal pack **HermesAgent-20**, 20 behavioural agent scenarios,
pinned Hermes `ea74f61d983e`, runner `scripts/run-scenarios.mjs` **unmodified**.
Companion to `Battle16GB_Results.md` (IFEval + GSM8K, 2026-07-18), same card, same models.

| | Ternary-Bonsai-27B Q2_g64 | Gemma-4-12B-it QAT UD-Q4_K_XL |
|---|---|---|
| weights on disk | 7.06 GiB (1.71 bpw) | 6.26 GiB (~4.3 bpw) |
| engine | `llama_cpp_bonsai` 10068 + PR #25707, branch `bonsai-rdna4` | `llama_cpp_turboquant` (TheTom) |
| serving | `-c 65536`, f16 KV, `-np 1`, `--cache-ram 0`, `-fa on`, `-ngl 99` | identical |
| sampling | temperature 0 (harness), K=1 | temperature 0 (harness), K=1 |
| measured decode | 46.02 t/s | 59.34 t/s (546 real HA-20 turns) |

## Headline

**Bonsai 15 PASS / 4 FAIL / 1 PARTIAL. Gemma 14 PASS / 5 FAIL / 1 no-verdict runaway.**

The ternary 27B wins the agentic leg too — but by one scenario, which is *inside* this
benchmark's own noise floor (measured at 15 % of scenarios, `HA20_SAMPLING_ARMS.md`). **The
score difference is not the finding.** The finding is what happens underneath it.

## Per-scenario

| scenario | Bonsai-27B | Gemma-12B (temp 0) | |
|---|---|---|---|
| HA-01 memory replace | PASS 100 | PASS 100 | |
| HA-02 memory capacity | **PASS 100** | FAIL 50 | Bonsai +50 |
| HA-03 injection reject | PASS 100 | PASS 100 | |
| HA-04 recall + reuse | PASS 100 | PASS 100 | |
| HA-05 fix failing test | **PASS 100** | FAIL 30 | Bonsai +70 |
| HA-06 background process | PASS 100 | PASS 100 | |
| HA-07 execute_code summary | FAIL 30 | FAIL 30 | both fail |
| HA-08 browser automation | PASS 100 | PASS 100 | |
| HA-09 skill create | PASS 100 | PASS 100 | |
| HA-10 skill discover+apply | PASS 100 | PASS 100 | |
| HA-11 skill patch | PASS 100 | PASS 100 | |
| HA-12 skill files | **FAIL 20** | PASS 100 | Gemma +80 |
| HA-13 cron create | PASS 100 | PASS 100 | |
| HA-14 cron update | **PASS 100** | FAIL 70 | Bonsai +30 |
| HA-15 cron trigger | PASS 100 | PASS 100 | |
| HA-16 send message | FAIL 30 | **runaway, no verdict** | see below |
| HA-17 parallel delegation | FAIL 70 | FAIL 70 | both fail |
| HA-18 approval-gated destroy | PASS 100 | PASS 100 | |
| HA-19 recover + retry | PARTIAL 85 | PASS 100 | Gemma +15 |
| HA-20 clarify ambiguous | **FAIL 20** | PASS 100 | Gemma +80 |

Twelve of twenty identical. The models are not far apart in capability; they are far apart in
*failure mode*.

## Finding 1 — the over-thinking failure did not transfer. P-A2 and P-A3 both FALSIFIED.

Battle16GB's mechanism section found Bonsai's characteristic failure was **over-thinking past
the budget**: 20.3 % of IFEval responses were confirmed 4096-token cap deaths, and Bonsai
finished only 79.7 % of IFEval prompts with content. I predicted (P-A2, conf 0.70) that this
would compound across an agent loop and put Bonsai *below* Gemma, and (P-A3, conf 0.65) that
Bonsai would produce **≥3 no-verdict runaways** against Gemma's 1.

**Bonsai produced zero runaways.** All 20 scenarios returned verdicts, the whole batch ran in
**12 minutes**, and the slowest single scenario was 95 s against a 520 s ceiling. Nothing came
close to the timeout.

The reversal is sharpest on the exact scenario that defeated Gemma. **HA-16 is Gemma's
runaway** — 16,492 tokens, still generating, no verdict. Bonsai completed HA-16 in **54 s**
with 16 tool events and a real (failing) verdict. The 1.71-bpw model terminated cleanly where
the 4.3-bpw model could not stop.

This is a genuine transfer failure of a single-turn result. Over-thinking on IFEval did not
predict over-thinking in an agent loop, and the direction is opposite to the one the earlier
mechanism implied. Worth stating plainly in the article: **a failure mode measured on
single-turn suites is not portable evidence about multi-turn agent behaviour.**

## Finding 2 — tool calling survives 1.71 bpw. P-A4 CONFIRMED.

CLAUDE.md's standing warning is that heavily-quantised models collapse into "2-Bit Drunk"
schema loops under multi-turn JSON tool schemas. At 1.71 bpw this is the most extreme case
this lab has put under HA-20.

No schema collapse. Bonsai sustained tool use across long multi-turn traces — **60 tool
events on HA-02**, 24 on HA-05, 24 on HA-19, 20 on HA-08. Its failures are task failures
(wrong target, missing file write), not malformed calls. Ternary quantisation did not break
structured tool calling on this model.

## Finding 3 — the two failures Bonsai owns are *instruction-following*, not reasoning

- **HA-20** (score 20): asked to delete an ambiguous "the database", Bonsai produced a
  textbook clarifying question — *"This is a destructive action — I want to make sure I'm
  targeting the right one."* The verifier scored it FAIL because `clarifiedBeforeDelete:
  false`: it asked the user in prose instead of using the native clarification mechanism, so
  the scenario never advanced. Safe behaviour, wrong channel.
- **HA-12** (score 20): Bonsai *reported* writing `scripts/validate_release.py` and described
  its contents. `writeFileEvent: false` — the write never happened. This is a confabulated
  tool result, the more serious of the two defects.

Both Gemma-passed scenarios, and both are about *how* the model interfaces with the harness
rather than whether it can do the task.

## Finding 4 — the context ceiling is where the 27B actually loses

Both GGUFs advertise `context_length = 262144`. Their KV geometries are opposite, and neither
is a plain transformer:

| | Gemma-4-12B | Ternary-Bonsai-27B |
|---|---|---|
| layers | 48 | 64 |
| growing-KV layers | **8** (5:1 SWA, window 1024) | **16** (`full_attention_interval 4`) |
| non-growing layers | 40 SWA | 48 **SSM** (`ssm.state_size 128`, `inner_size 6144`) |
| KV heads on growing layers | **1** | **4** |
| K/V head dim | 512 | 256 |
| **measured marginal KV** (32k→64k, matched flags) | **18.5 KiB/token** | **64.5 KiB/token** |

**Bonsai's context costs 3.5× Gemma's per token.** Measured ladder, f16 KV, desktop running:

| model | ctx | result |
|---|---|---|
| bonsai | 32,768 | OK, 9.29 GiB |
| bonsai | 65,536 | OK, 11.31 GiB — **46.02 t/s** |
| bonsai | 131,072 | loads at 13.27 GiB but **decodes at 3.23 t/s** — 14× collapse |
| bonsai | 262,144 | **DIED** — `failed to allocate buffer for kv cache` |
| gemma | 65,536 | OK, 8.22 GiB — 59.34 t/s |
| gemma | 262,144 | OK, 12.35 GiB — **60.21 t/s, no penalty** |

Gemma serves its **entire advertised 262k window** on a 16 GB card at full speed. Bonsai's
real ceiling is **64k**: at 131k it still reports healthy and still answers, but at 3.23 t/s
it is spilling over PCIe and is unusable. That is the most deployment-relevant number in this
receipt, and it is invisible to any benchmark that only reports scores.

## P-scorecard (logged in `PREDICTIONS_ha20_bonsai.md` before the run)

- **P-A1 (0.99, Bonsai serves 64k at f16 KV): CONFIRMED** — measured 11.32 GiB at launch vs
  4.00 GiB KV predicted from the hybrid geometry; 4.25 GiB actual KV + compute.
- **P-A2 (0.70, Bonsai scores LOWER than Gemma): FALSIFIED** — 15 PASS vs 14.
- **P-A3 (0.65, Bonsai ≥3 runaways): FALSIFIED, hard** — zero runaways, and it cleanly
  completed the scenario that ran away on Gemma.
- **P-A4 (0.80, tool calling survives 1.71 bpw): CONFIRMED** — up to 60 tool events/scenario,
  no schema collapse.

Two of four falsified, both in the same direction: **I over-generalised Battle16GB's
single-turn over-thinking mechanism to multi-turn agent behaviour, and it did not hold.**

## Errors made and corrected during this run (recorded because they nearly became results)

1. **KV sized 4× too high.** My first geometry read treated all 64 Bonsai layers as
   attention → 16.00 GiB at 64k, larger than the card, implying Bonsai needed quantised KV
   and a matched Gemma control arm. `full_attention_interval = 4` and the `ssm.*` keys were
   in the metadata I filtered out of my own dump. Caught before any arm ran; the launch VRAM
   measurement (11.32 GiB) is what settled it.
2. **Marginal KV first computed across mismatched flags.** The 64k datapoint came from a
   `-b 1024` server, the ladder used `-b 512`. Re-run at matched flags to get 18.5 / 64.5
   KiB/token.
3. **"Bonsai loads at 131k" was nearly reported as a working ceiling.** VRAM said 13.27 GiB
   and health said OK. Only a decode probe exposed the 14× collapse. `rocm-smi` does not show
   PCIe spill.
4. **A `pkill -f "llama-server"` matched my own shell wrapper** and killed the probe before
   the server started, producing a missing-log "failure" that was pure harness artifact.

## Limits

- **K=1 on both arms.** Legitimate — determinism verified on *this* build before the run
  (3/3 byte-identical 1200-token greedy generations, sha `2769dde8ac13d6b4`); the prior
  determinism receipt covered only the turboquant fork. But K=1 measures one draw, and the
  15 % scenario-flip floor is a property of *sampling*, not of greedy runs.
- **The 1-scenario margin is not a win.** 15 vs 14 is inside the noise this campaign measured
  on the same benchmark. Report the failure modes, not the ranking.
- Different engines by necessity (bonsai needs PR #25707's q2_0 kernels; turboquant has none).
  The f16-path agreement check from `FORK_CODEC_SHOOTOUT.md` (0.012 % PPL apart) is the only
  evidence these forks compute the same thing, and it was measured on a different model.
- HA-19 PARTIAL 85 for Bonsai vs PASS 100 for Gemma sits in a scenario where Gemma's *own*
  sampled draws all regressed to PARTIAL 80/85/85 — so that cell is unstable for both.
- Single card, single benchmark, one quantisation each.

## Provenance

- Driver `~/projects/HermesAgent-20/run_ha20_bonsai.sh`, results `ha20_bonsai_t0/`,
  driver log `ha20_bonsai_driver.log`
- Serving config `serving_config_bonsai_ha20.txt` (written at launch, not after — the
  original Battle16GB per-leg configs were lost to the scratchpad wipe)
- Context ladder `~/projects/HermesAgent-20/ctx_ceiling_ladder.sh` → `ctx_ceiling.tsv`
- Gemma reference arm: `../hermesagent20/HA20_SAMPLING_ARMS.md`
