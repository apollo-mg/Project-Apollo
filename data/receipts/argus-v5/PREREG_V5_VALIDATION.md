# Pre-registration — families_v5 validation pass (world B isomorph)

**2026-09-24, before any v5 inference.** RX 9070 XT, buun `38ada0e1b`, `Qwen3.8-27B-UD-IQ3_XXS`, MTP OFF,
seed 1, prompt cache OFF, runner `argus/run_argus_v5.sh val OFF-s1:0:1`. Corpus `argus/families_v5.json`
(83 items), built by `argus/build_families_v5.py`.

## What v5 is

- **World A:** the 40 families_v4 items, byte-identical apart from a `world: "A"` tag, on the
  unchanged world-A fixture.
- **World B** (`argus/worlds/B/`): an isomorph of world A. It has the same calendar geometry and the
  same ambiguities (two contacts sharing a first name, two contacts at one company), with every name,
  company, subject and file renamed. It carries 40 **twins** (`B-` ids, `twin_of`) and 3 **extras**
  covering structures world A is too thin for: an ask-side f3 rung 4, and f5 rungs 3 and 4.

Build-time checks, all passing:
- every twin decides the same expected kind with the same grounding floor as its template;
- `verify_families.py` is clean on both worlds (40/40, 43/43, boundaries 9/9);
- the stripped world-B state carries no authoring notes.

**Prior art checked:** `ledger_precheck.py "argus corpus expansion world isomorph twin items"` -> the
corpus design receipts (`RESULT_BRACKET_CONCENTRATION.md`, `RESULT_FIXTURE_COMPUTED_FAMILIES.md`,
`A1_MEASUREMENT_CORPUS_SPEC.md`) cover rung design within one world.
It also surfaced three INDEX receipts:
- L197: v2 items machine-decided against the world, the method reused here.
- L203: LLM-generated corpus items failed ("cannot hold an abstract constraint"), which is why v5 is
  *computed*, not generated.
- **L283: Qwen3.8-27B over-acts on ~46 % of ambiguous requests, and nearly all discriminating variance
  sits in the ask items.** That is consistent with the MTP flips (9 of 11 worse were `WRONG-ACTION`), and
  it argues that any *further* expansion should weight ask-side items. A second world with verified twins
is new. It is also a **surface-invariance test**: does the same judgement survive a renaming?

## What this pass must show before v5 is used for any comparison

| gate | pass condition |
|---|---|
| V1 | World-B gate rungs (r1) pass at least as often as world A's, minus one item |
| V2 | No world-B item is INFRA or SUSPECT where its twin is not. Systematic ones get fixed, and the pass re-runs |
| V3 | No UTC-date rollover (the run must end before 00:00 UTC) |

## Measured, and the input to the MTP-harm prereg's power calculation

- **Twin concordance:** the share of the 40 templates where the A item and its B twin get the same
  pass/fail. High concordance means twins behave like one unit and inference must cluster by template.
- World A pass rate vs world B pass rate (surface invariance), with an exact McNemar test over the 40
  pairs.

**Prediction:** twin concordance ≥ 80 % (conf 0.6). Pass-rate difference A-B within ±10 pp (conf 0.7).

## Not established

One seed, one model. This validates the instrument; it compares nothing else.

## Deviation 1 — 2026-09-24 ~13:55, after 26 of 83 items

The arm stopped after `f6-inconsistent-r2` (exit 5, AFM-44 guard): a new listener `127.0.0.1:33665` appeared, owned
by a `python3` from **Hermes Desktop, launched by Mark on the host at 13:45:17** (systemd user unit). The item
ended at 13:45:59. The guard diffs listeners host-wide, so it cannot tell the operator's apps from the agent.

**Fix (`argus/driver.py`):** a new listener counts as the agent's leftover unless its process is in the driver's
own PID namespace. The agent runs under `bwrap --unshare-pid`, and all its descendants are in a child namespace
(verified: host `pid:[4026531836]`, sandbox `pid:[4026533230]`). Unknown or unreadable PIDs still count as
leftovers. Host-namespace listeners are recorded in `host_new_listeners_unrelated`.

No scoring change. The 26 completed rows stand. The run resumes on a fresh server (same seed; warmup discarded).
