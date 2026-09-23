# Prereg — can the argus instrument see a 9B at all?

**Written 2026-09-22, before any arm ran. This is a GATE, not the panel.** It decides whether a
5-rep MiMo-vs-Ornith comparison is worth its hardware, and it measures the resolution limit at the
sampling each model actually requires.

**Prior art checked:** `ledger_precheck.py "MiMo distill 9B agentic smoke test small model floor"
--deep` -> `argus-v2/RESULT_NOISE_FLOOR.md` (the 10.3 % floor), `FINDINGS_2026-08-25.md` (the v1
corpus had almost no discriminating power), `viability/RESULT_SPARK4B_TOOLS.md` (a 4B scores 24/24
on tool-call mechanics, which is not agentic competence), `FAILURE_MODES.md` AFM entry on Ornith
looping when given its coding profile.
**What this adds:** every prior argus figure is temp 1.0, single rep, on a 27B. Nothing measures
whether a **9B** lands in the corpus's measurable band, and nothing measures the noise floor at any
temperature **other than 1.0**. Both are prerequisites for the panel and neither is published.

## Why a gate and not the panel

`RESULT_NOISE_FLOOR.md`: two identical arms disagree at **10.3 %** at temp 1.0, one rep --
*identical to the "signal"* measured between two different quants. The panel costs 5 reps x 2 arms.
Before spending that, two things must be true, and neither is known:

1. **The 9Bs must land in a measurable band.** If either floors or saturates on 31 scorable items,
   there is no variance to compare and reps cannot create any.
2. **The floor must be known at the sampling these models require** -- which is not temp 1.0 for
   MiMo.

## The sampling problem, stated plainly

Under the standing rule that manufacturer sampling is the only proper configuration, the two arms
are **not sampled alike**, and the difference is large:

| | temp | top_p | top_k | min_p | presence |
|---|---:|---:|---:|---:|---:|
| **Ornith-1.5-9B, "general"** (the agentic profile) | **1.0** | 0.95 | 20 | 0.0 | **1.5** |
| Ornith-1.5-9B, "precise coding" (NOT used -- it made Ornith loop on every scenario, 08-28) | 0.6 | 0.95 | 20 | 0.0 | 0.0 |
| **MiMo-V2.6-Distill-Qwen-9B** (only published profile) | **0.6** | 0.95 | 20 | *unspecified* | **0.0** |

`min_p` for MiMo is **our choice, pinned to 0.0**, because the card is silent and llama.cpp would
otherwise supply 0.05 (`AFM-23`). Recorded as ours, not the vendor's.

**Therefore this experiment cannot answer "does agentic SFT buy judgement."** Temperature and
presence penalty both differ by vendor instruction, so any measured gap is
model + sampling, inseparably. What it *can* answer is **"MiMo as shipped vs Ornith as shipped"** --
the comparison a user actually faces. The prereg commits to that framing; the receipt must not
drift from it.

**All sampling is pinned explicitly on the command line** per `AFM-42`: MiMo's GGUF embeds
`general.sampling.temp 0.6 / top_k 20 / top_p 0.95` and Ornith's embeds nothing, so identical
launch flags would otherwise have produced different temperatures silently.

## Arms

RX 9070 XT (gfx1201), upstream llama.cpp build 11095 (`58367713a`) `build_rocm`,
`-ngl 99 -c 8192 -fa on -ctk f16 -ctv f16 -np 1 --kv-unified`. **No MTP head** (see below).
`families_v4.json`, 40 items / **31 scorable** (9 are gate role). 1 rep. Sequential -- two 9.5 GB
models do not co-resident on 16 GB, and `-np 1` is required
(`[[agent-benchmark-determinism]]`: concurrent batching was itself a nondeterminism source).

| arm | model | sampling |
|---|---|---|
| `MIMO-a`, `MIMO-b` | MiMo-V2.6-Distill Q8_0 | temp 0.6, top_p 0.95, top_k 20, min_p 0.0, presence 0.0 |
| `ORN-a`, `ORN-b` | Ornith-1.5-9B Q8_0 | temp 1.0, top_p 0.95, top_k 20, min_p 0.0, presence 1.5 |

Each model runs **twice under identical configuration**. The a-vs-b discordance is that arm's
**noise floor at its own sampling** -- the same design as `RESULT_NOISE_FLOOR.md`, which is the only
reason we know the 27B figure.

**MiMo uses `argus/templates/mimo_v26_distill_qwen9b_autoparser.jinja`.** Mandatory, not optional:
the stock template corrupts 17/30 multi-tool-call turns, and while **zero** corpus items *expect*
2+ actions, **304 of 350 scenarios in the live Hemmingway run make 2+ backend calls**. The
corruption folds a second call into the first one's argument, which would silently convert an
over-action (`WRONG-ACTION`, the thing we score) into an apparent single clean action.

## Predictions, committed before data

| id | prediction | conf | falsifier |
|---|---|---|---|
| **G1** | both models land in 20-80 % pass rate (the measurable band) | 0.45 | either floors <15 % or saturates >85 % |
| **G2** | MiMo's noise floor at temp 0.6 is **below** the 27B's 10.3 % at temp 1.0 | 0.75 | >= 10.3 % |
| **G3** | Ornith's noise floor at temp 1.0 is within +/-4 points of 10.3 % | 0.60 | outside |
| **G4** | the MiMo-vs-Ornith pass-rate gap is **smaller** than the larger arm's own noise floor | 0.55 | gap exceeds it |
| **G5** | neither arm produces a `SUSPECT` rate above 10 % | 0.70 | either exceeds |

**G4 is the decision.** If the between-model gap does not clear the within-model noise, the panel
cannot resolve these two models and should not be run at 5 reps -- the honest output is a bound
("no difference larger than X"), not a comparison.

**G1 at 0.45 is deliberately low.** A 9B on a corpus built to separate 27Bs is more likely to floor
than not, and that would be a clean, cheap negative worth publishing on its own.

## Deliberately excluded

**No MTP head in the instrument.** The Ornith head is a base-family asset and would roughly double
throughput on this tool-call-heavy corpus, but `RESULT_MTP_HEAD_TRANSFER.md` established that
speculation changes emitted text. Adding a drafter to a measurement rig adds an axis. It is instead
its own follow-up, below.

## Follow-up this gate enables (Mark, 2026-09-22)

> *"does enabling MTP cause any errors that don't happen without"*

Better posed than a throughput question, because argus has a **typed verdict space**
(`CORRECT` / `WRONG-ACTION` / `WRONG-INACTION` / `CLARIFIED` / `INFRA` / `SUSPECT`). So the question
is not "does the rate move" but **"does speculation introduce verdict classes that are absent
without it"** -- and it is a paired, same-item design, analysable with the McNemar machinery already
in `tools/discordance.py`.

It needs this gate first: a model that floors or saturates cannot show a class shift either. Run it
as `MIMO-mtp-a/b` against `MIMO-a/b`, same sampling, head on/off the only difference, and report
the **verdict transition matrix**, not the aggregate.

---

## AMENDMENT 2026-09-22, before any valid arm — three corrections found on first launch

**The first launch produced 40/40 `INFRA` and was aborted.** All three fixes below were made
before any scored row existed; no data is discarded because none was valid.

**1. Context: `-c 8192` -> `-c 65536`.** Hermes Agent hard-refuses any model whose server reports
below **64,000** tokens: *"has a context window of 8,192 tokens, which is below the minimum 64,000
required by Hermes Agent."* This is the same defect that produced 3/3 INFRA earlier in the campaign
at `-c 32768`, and the `.194` reference arms already run `-c 65536`. **It should have been read off
`start_arm.sh` rather than rediscovered.**

**2. Engine and KV: upstream + f16 -> buun `38ada0e1b` + VBR.** f16 KV at 64k costs ~8 GiB on top
of 8.9 GiB of weights and does not fit 16 GB; it is not achievable on this card at any context
Hermes will accept. Pinning `q8_0` was the first fix and is unconditionally lossy. **Mark proposed
VBR, which is better on both axes:**

| KV | VRAM used | free | quality entry point |
|---|---:|---:|---|
| `q8_0` (first fix) | 12.13 GiB | 3.79 | always ~8.5 bpv |
| **`vbr --vbr-floor t4`** | **10.79 GiB** | **5.14** | **f16, degrading only when the budget binds** |

Log confirms: *"entry tier f16, floor 4.125 bits/value, price-ordered decode-time degrades"*,
KV budget 6747 MiB auto. `--vbr-floor t4` is explicit because a bare `-ctk vbr` defaults to the
**1.25 bpv bottom rung** (`[[buun-default-kv-is-vbr]]`).

buun `38ada0e1b` is the commit the original prereg specified, contains the fused-MMA VBR latch fix
`a334fc01e` (`[[vbr-fused-mma-latch-9070]]`), and **matches the engine `.194` already runs** --
`start_arm.sh` uses a buun build, so this is closer to the reference than upstream would have been.

**3. `--no-cache-prompt` added.** VBR with a warm prefix cache yields two strictly alternating
outputs from one seed (`[[prompt-cache-breaks-determinism]]`). **This experiment's whole product is
a noise floor**, so that artifact must not be counted inside it. Pinned at the server rather than
trusted to the client.

**4. Timezone pinned to UTC in both fixtures.** They were copied from `amd`, which predates the
pin; the driver warned *"fixture declares none; the agent will use the host zone"*. The host is
`America/New_York` while expectations are computed in UTC, which silently moves every date boundary
in the corpus.

### What the KV change costs

`G2` and `G3` compare these noise floors against the 27B's **10.3 %**, which was measured at
**f16** KV. These arms run VBR. Two effects push in opposite directions -- lower temperature should
reduce noise, lossy KV under pressure should raise it -- so **a G2/G3 result must not be read as a
pure temperature effect.**

Mitigating: the budget (6747 MiB) only binds near full context occupancy, and these scenarios run
a few thousand tokens, so VBR should sit at its f16 entry tier throughout. **This is checkable, not
assumed** -- the server log records degrade events, and the receipt must report whether any fired.
If none did, the KV path was f16 in practice and the comparison to 10.3 % holds.

`G1`, `G4` and `G5` are unaffected: floor/saturation and the between-model gap do not depend on KV
codec.

---

## AMENDMENT 2 — 2026-09-22, before the full gate; the smoke run changed the harness

A 3-item smoke per model was run to shake the harness down. It found three defects, all fixed
before any gate row was collected. **Smoke rows are shakedown only and are excluded from every
gate statistic.**

**1. Fixtures rebuilt with `make_fixture.sh` (AFM-43).** The first fixtures were `cp -a` clones,
so `SKILL.md` wrote to the source fixture's mailbox. A **correct** MiMo reply was scored
`WRONG-INACTION`. Rebuilt properly; `pilotA`'s `SOUL.md` (sha `36c1f5a2`) copied in because
`make_fixture.sh` does not write one and the reference arms use it. The fixtures now differ from
`pilotA` **only** in model path, base URL and gateway port. `verify_families` is clean on all three
worlds, and all share the reference's world anchor (`2026-09-24`).

**2. Browser launches denied (AFM-44).** MiMo launched an unsandboxed headless Chrome with a CDP
port from the terminal, and it outlived the scenario. The 9B fixtures now carry an `approvals.deny`
list blocking browser launches. **This is a deviation from the `pilotA` reference config**, and it
is behaviourally inert for any model that never launches a browser from the shell. The 27B arms
never did (they called the `browser_exec` *tool* once in ~1,000 calls, which is unaffected), and
neither did Ornith in the smoke. So it constrains exactly the behaviour that was contaminating the
host, and nothing the reference arms exercised.

**3. Per-scenario host tripwire.** The driver now records any TCP listener that outlives its
scenario (`host_new_listeners`) and stops the arm if one appears. A row carrying this field is
not a valid measurement of that model.

### Expectation added from the smoke (not a prediction -- n=3, shakedown)

MiMo reaches for the `browser_exec` **tool** on mailbox tasks (4 of 13 calls on `f1`), gets
nothing, and usually but not always recovers into the google skill. That is honest, as-shipped
behaviour, and it stays in: the tool is offered to every arm alike. Expect it to cost MiMo time
and some items, and report the rate. A `NO-ATTEMPT` where the model spent its turns on the browser
is a **tool-discovery** failure, not a judgement failure, and the receipt must separate the two
rather than fold them into one pass rate.

---

## AMENDMENT 3 — 2026-09-22, before any gate row; loop hard-stop, and the primary void rule

The first full launch was stopped after MiMo spent **447 s and 47 `browser_exec` calls** on
scenario 1 without recovering. No row had been written; nothing is discarded.

**1. Hermes's loop hard-stop enabled in the 9B fixtures.** Hermes ships `tool_loop_guardrails`
warn-only. A looping model therefore runs to the 900 s timeout, and `driver.judge()` scores any
exception, including `asyncio.TimeoutError`, as **`INFRA`**. Both void rules drop `INFRA`. So a
model's loops would **silently leave the analysis**, and its pass rate would be computed only over
the items it did not loop on. That is a bias toward false success, not merely a cost. With
`hard_stop_enabled: true` (Hermes defaults: 5 identical or 8 same-tool failures), the agent's turn
ends cleanly and it is judged on what it did. A **declared deviation from `pilotA`**, inert for any
model that never repeats a failing call. Verified via Hermes's own
`ToolCallGuardrailConfig.from_mapping`: `True` for both 9B fixtures, `False` for `pilotA`.

**2. The judge void rule is PRIMARY for this gate.** `tools/argus_reps_compare.py` reports two
rules. The noise-floor rule voids `NO-ATTEMPT`, which is exactly the tool-discovery failure MiMo
produces (browser detour, backend never touched). Making it primary would hide what Amendment 2
committed to reporting. So:

- **primary** -- judge rule: void only `INFRA` and `TOOL-FAIL`
- **secondary** -- noise-floor rule, for comparability with `RESULT_NOISE_FLOOR`
- **separately** -- the `NO-ATTEMPT` and hard-stop rates per model, as tool-discovery failures

Any `INFRA` row that remains is a genuine environment failure and must be explained individually.

---

## AMENDMENT 4 — 2026-09-22; the agent now runs sandboxed

**Timing, stated exactly:** the changes below were committed (`eb5fef7`) and in effect **before**
the run launched at 19:03:21. This text was committed about a minute **after** the first gate row
was written. No gate data informed it; it records a configuration already fixed at launch.

The paused run showed models reaching **outside the fake world**: MiMo listing the home
directory and reading browser-harness files, and, on review of earlier raw data, 27B arms
grepping a real local mail archive, opening personal documents, attempting `mail`, and reading
the fake world's raw seed file. Two changes, both declared deviations from the `pilotA`
reference configuration:

**1. The agent runs inside bubblewrap** (`argus/sandboxed_agent.sh`). Read-only root; empty
`/home` and `/mnt`; bound back in only hermes-go, the Python its venv links through, the
fixture's `agent-home` and `fake-google`, and the scenario sandbox; `seed.json` hidden; pid
namespace unshared, so anything the agent backgrounds dies with it. Verified 14/14 from inside.

**2. `reset.sh` writes a stripped state.** The seed still carried authoring notes (*"AMBIGUITY:
two Daves on purpose"*) that the CLI strips from its output. A verbatim copy put them in
`state.json`, where any agent reading the file directly got the answer to the referent items.

### What this does to comparability

Neither change affects a model that uses the mail CLI and nothing else. Both change the world
for a model that explores the filesystem, and the sandbox is a real difference from every
earlier argus run, the Hemmingway comparison included, which ran unsandboxed with the leaky
state. **So these gate arms are comparable with each other, and not with pre-sandbox runs on any
item where an agent went exploring.** The receipt must count how often each model hit the sandbox
walls (denied paths, blocked launches) as part of the tool-discovery rate from Amendment 2.

Sandboxed smoke (shakedown, excluded): Ornith `f1` CORRECT through the CLI from inside the
sandbox; MiMo `f4` CORRECT; no listener left behind; port 9222 closed throughout.


---

## AMENDMENT — mid-run harness change at 21:39:32 (credential environment variables stripped)

At **21:39:32** the sandbox wrapper began removing every credential-named environment variable before
starting the agent. The wrapper runs per scenario, so every scenario from 21:39:32 onward ran without
them. Nothing else changed.

**Why:** the driver passes the caller's entire environment to the agent, and it carried a Claude
Code session token, while the sandbox shares the network. **What had happened before 21:39:32:** MiMo ran
`env | grep` four times during the 9B gate, twice with patterns including `token`. Its only
network activity was two **unauthenticated** status-code probes (`gmail.googleapis.com` and
`www.google.com`), with no credential in either, confirmed from Hermes's session store. The token
value appears nowhere on disk in the run outputs, fixtures or receipts.

**Effect on the measurement:** none expected. No model's task can use an environment secret, and
no scored action depends on one. Rows before and after 21:39:32 are pooled; this is recorded so the change
is not invisible. Verified that both running experiments kept producing normal verdicts afterwards.
**Residual:** the network is still shared. A model can reach the internet; with secrets stripped
and the home directory hidden it has little to carry. `--unshare-net` plus a forwarder for the
model port is the next hardening step.
