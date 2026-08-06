# Lab Spec: Puzzle-75B Evaluation Campaign (W1–W3)

**For:** Gemini (executor). **Spec:** Claude/Fable (Architect). **Owner:** Mark.
**Date:** 2026-07-13. **Prerequisite state:** Phase 1–5 of `Lab_Brief_Puzzle75B_DynQuant.md`
complete; UD-IQ4-XL crowned deployment pick; receipts in `.194:~/puzzle_lab/`.

Three workstreams, run in order. W1 decides the publishable brittleness claim. W2 audits
NVIDIA's concurrency positioning on our hardware. W3 produces the capability verdict and the
community-legible benchmark layer.

---

## §0 REPORTING CONTRACT (read first; violations void the report)

These gates exist because each one was violated at least once this week. They are not
decoration.

- **G1 — Every number cites a receipt.** Any number in any report must be followed by the
  absolute path of the on-disk log it came from. A number with no path is treated as
  fabricated, and the whole report is rejected — not just that line.
- **G2 — Artifacts must exist.** Naming a file ("see report.md") requires pasting `ls -l`
  output of that file, from the machine it lives on, in the same message. A referenced file
  that does not exist at the stated path is a contract violation. **Campaign artifacts must
  live under the repo or the spec-named receipts dirs (`~/puzzle_lab/...`). Files in
  agent-private storage (e.g. `~/.gemini/.../brain/`) do not exist for campaign purposes** —
  they are outside receipts custody and unverifiable by the Architect. (Added 2026-07-13
  after the final_campaign_report incident.)
- **G3 — No invented mechanisms.** Reports contain OBSERVATIONS (with receipts) and, in a
  separate clearly-marked section, SPECULATION. A hardware/dispatch claim ("X happens because
  the GPU lacks Y") may only appear as observation if backed by a source-code path or a
  measured receipt. When in doubt, write "cause unknown" — that is always an acceptable answer.
- **G4 — Quote verbatim or don't quote.** When scoring a prediction, copy the prediction text
  from §5 of this spec character-for-character before scoring it. Do not paraphrase, round,
  or add numbers that are not in the quoted text.
- **G5 — Exact commands only.** Run the command lines written in this spec. Any flag change,
  addition, or omission — including "harmless" ones — requires STOP, report the reason, and
  wait for approval. (History: `--split-mode row` on P100s, `-ub 2048` on a 2-card split,
  `-b 256` overrides on cert runs. All three burned hours.)
- **G6 — Two failures = stop.** Any step failing twice stops the workstream. Report the two
  failures verbatim (full error text) and wait. Do not improvise a third variant.
- **G7 — Deviating results are findings.** A number that looks wrong is reported verbatim
  with its receipt, not re-run until it looks right. If you re-run anything, report every
  run, including the ones you liked less.
- **G8 — Report completion = receipts manifest.** A workstream is "done" when its report
  ends with a manifest: every receipt file, `ls -l` + md5sum. No manifest, not done.

Standing rules (unchanged): `llama-cli` from the puzzle build is BANNED. Nothing else runs on
the measured GPUs during a leg (`nvidia-smi` check before each). Never touch
`~/carveout_panel/`, `~/moe_panel/`, `~/phaseb/`, `~/qwen-base-logits-kld/`,
`~/tom_validation/`. Puzzle Q8_0 shards are KEPT until Mark signs the final campaign report.
Delete nothing without listing it and receiving an explicit yes.

Receipts layout for this campaign: `.194:~/puzzle_lab/w1/`, `~/puzzle_lab/w2/`,
`~/puzzle_lab/w3/` (create as needed).

---

## §1 W1 — Dense control (decides the NAS-brittleness claim)

**Question:** Puzzle-75B at Q4_K_M loses 6.0% of greedy tokens vs its own Q8 (same-top
94.010%, receipt `~/puzzle_lab/kld_q4km.log`). Is that NAS-pruning brittleness, or just what
Q4 costs any modern hybrid? Control: same protocol on Qwen3.6-27B.

**Downloads** (to `~/AI/Models/Qwen 3.6/27B/`): official-source GGUFs of Qwen3.6-27B
**Q4_K_M** and **Q8_0**. Before downloading, fetch exact byte sizes from the HF API tree
endpoint, save to `~/puzzle_lab/w1/expected_sizes.txt`, verify after download with `stat -c%s`
(G1: log to `~/puzzle_lab/w1/download_verify.log`). If multiple community repos exist, prefer
the same publisher as the existing Q6_K box model; report your choice + repo URL before
downloading.

**Build:** `~/llama_stock/build_carveout` (the panel-proven Qwen binary — NOT the puzzle
build). Verify `--version` prints `4f37f5197`-lineage before use; log it.

**Runs** (all: wikitext-2 `~/wikitext-2-raw/wiki.test.raw`, md5 must verify
`7c0137fc034ddbc56a296bce31b4f7fb`; 2048 ctx / 32 chunks; f32 KV; FA off; 4-card):

```bash
# 1. Truth base from Q8_0 (fits fully on GPU: ~29GB over 4 cards)
~/llama_stock/build_carveout/bin/llama-perplexity \
  -m <Q8_0.gguf> -f ~/wikitext-2-raw/wiki.test.raw -c 2048 --chunks 32 \
  -ctk f32 -ctv f32 -fa off -ngl 99 -ub 128 \
  --kl-divergence-base ~/puzzle_lab/w1/qwen27b_q8truth_f32kv_faoff_2k32.kld \
  2>&1 | tee ~/puzzle_lab/w1/truthbase_qwen_q8.log

# 2. Score Q4_K_M against it (same flags, add --kl-divergence)
~/llama_stock/build_carveout/bin/llama-perplexity \
  -m <Q4_K_M.gguf> -f ~/wikitext-2-raw/wiki.test.raw -c 2048 --chunks 32 \
  -ctk f32 -ctv f32 -fa off -ngl 99 -ub 128 \
  --kl-divergence --kl-divergence-base ~/puzzle_lab/w1/qwen27b_q8truth_f32kv_faoff_2k32.kld \
  2>&1 | tee ~/puzzle_lab/w1/kld_qwen_q4km.log
```

Also read both models' `quantize.imatrix.*` header keys (venv python + gguf-py, method proven
2026-07-12) and record in `~/puzzle_lab/w1/imatrix_check.txt` — if the Qwen Q4_K_M is
imatrix-free while Puzzle's was imatrix'd, that asymmetry goes in the report caveats, in the
observation section, with the key dump as receipt.

**Deliverable:** the full final stat blocks (verbatim) for the Q4 cell + a two-row table
Puzzle-vs-Qwen (median KLD, same-top, both with receipt paths).

---

## §2 W2 — Concurrency scaling (audits the vendor positioning)

**Question:** NVIDIA positions this model for concurrent multi-agent serving (8×1M-token
requests on one H100 claimed). What does concurrency actually cost on the pooled quad at the
deployable quant?

**Server** (build_puzzle, UD-IQ4-XL, known-good split). One server instance per np value,
sequential, never two at once:

```bash
~/llama_stock/build_puzzle/bin/llama-server \
  -m ~/AI/Models/Nemotron/Puzzle-75B/Puzzle-75B-A9B-UD-IQ4-XL.gguf \
  -ngl 99 -ts 1,0.72,1.14,1.14 -ub 128 -np <N> -c <N*8192> \
  --port 8091 2>&1 | tee ~/puzzle_lab/w2/server_np<N>.log
```

N ∈ {1, 2, 4}. **Do NOT pass `--kv-unified`** in the base sweep — llama.cpp has a known
hybrid-model cache-drop bug under `-np 2 --kv-unified` (found during the sidecar campaign,
reproduced on unpatched buun, reported to TheTom). An optional final leg MAY repeat np=2 with
`--kv-unified` to check whether this arch reproduces the bug — label that leg explicitly.

**Load driver:** a fixed prompt file (`~/puzzle_lab/w2/prompts.txt`, 8 prompts, ~600 tokens
each — write once, reuse for every N). For each N: fire N simultaneous curl requests
(temp 0, max 256 tokens each), wait for all, repeat 3 rounds. Record per-request timings from
the server log (`prompt eval time` / `eval time` lines are the receipts) into
`~/puzzle_lab/w2/results_np<N>.txt`.

**Metrics per N (each with receipt path):** per-slot decode t/s (mean of rounds), aggregate
decode t/s (sum of concurrent slots), time-to-first-token per slot, VRAM per card after model
load and after all slots warm (`nvidia-smi` snapshots, saved), and the server-log line
reporting KV/state buffer sizes.

**Failure handling:** if np=4 fails to allocate at `-c 32768`, halve per-slot ctx to 4096
(`-c 16384`), note it, continue (G5 exception pre-authorized here only). Watch for and report
verbatim any `cache` / `slot` warnings — with this arch they are findings (G7), not noise.

**Deliverable:** scaling table N × (per-slot tg, aggregate tg, TTFT, VRAM), plus the
efficiency line: aggregate(N)/aggregate(1).

---

## §3 W3 — Task A/B + community benchmark layer

**Question:** deployable-vs-deployable capability: Puzzle-75B UD-IQ4-XL vs Qwen3.6-27B Q8_0
(W1's download), both served from .194, measured through the same harnesses.

**Serving:** one model at a time on .194 (llama-server, port 8091). Puzzle: flags as W2 with
`-np 1 -c 16384`. Qwen: `~/llama_stock/build_carveout` server, `-ngl 99 -c 16384`, its proven
chat template from `profiles.yaml` conventions. For EACH model record into
`~/puzzle_lab/w3/serving_config_<model>.txt`: exact command line, chat template file + md5,
sampling params, and **thinking channel state (on/off) — pinned OFF for both models in all
W3 runs** (rationale: symmetric budget; a thinking-on addendum may follow later as its own
labeled leg).

**Suites** (run from the desktop against the endpoint; pin and record harness git commits):

1. **IFEval** (full set) — objective string checks, greedy.
2. **GSM8K, fixed 250-question subset** — greedy; generate the subset ONCE with seed 42,
   save question IDs to `~/puzzle_lab/w3/gsm8k_subset_ids.txt`, reuse for both models.
3. **BFCL** (function-calling) — the single-turn AST categories minimum; more if runtime
   allows. This is the multi-agent claim's proxy and maps to the known Q4 schema-brittleness
   axis.

No LLM-judged suites. No MMLU-scale marathons. If a harness needs a config/template decision
not specified here: STOP and ask (G5), do not guess silently.

**Reporting frame:** deltas, not absolutes — each suite reported as
`Puzzle-UD-Q4 | Qwen-Q8 | NVIDIA-published BF16 (where available, with source URL)`. Every
score row carries the results-file path (G1). Raw harness output directories are the
receipts; tar them into `~/puzzle_lab/w3/raw/`.

**Deliverable:** one table (3 suites × 3 columns + receipts column) + observation/speculation
split per G3.

---

## §4 Sequencing, time, and machine discipline

W1 → W2 → W3 strictly. W1 blocks the brittleness writeup; W2 needs no downloads (can start
while W1 models download, but never share GPUs with a W1 measurement leg); W3 needs W1's Q8
download and harness wiring on the desktop. .73 stays out of this campaign (it is the loaner
box; its cert is signed). CHANGELOG `[Unreleased]` entry after each workstream completes,
per house protocol.

---

## §5 Predictions (Claude/Fable, logged 2026-07-13 BEFORE any W1–W3 run; score against this
text verbatim, per G4)

- **P-W1:** "Qwen3.6-27B Q4_K_M scores same-top ≥ 97.5% against its own Q8_0 truth base
  under the identical protocol — i.e., the dense-ish control shows Puzzle's 94.0% to be
  NAS-anomalous, not generic Q4 cost. Confidence: moderate. If Qwen lands ≤ 95%, the
  brittleness claim dissolves and the writeup angle becomes 'Q4 costs more than the community
  assumes on modern hybrids.'"
- **P-W2:** "Aggregate decode throughput at np=4 reaches at least 2.0× np=1, and per-slot
  state+KV cost is small enough that 4×8k slots fit without allocation failure. Confidence:
  moderate. Separately, flagged as watch-item, not prediction: hybrid slot-cache warnings may
  appear at np≥2 even without --kv-unified."
- **P-W3:** "Puzzle-UD wins GSM8K-250 (parent-scale knowledge survives Q4), while Qwen-27B-Q8
  ties or wins BFCL and IFEval (quant brittleness expresses first at schema/instruction
  boundaries). Confidence: low-moderate. A Puzzle sweep of all three would genuinely surprise
  me and would upgrade the deployment verdict from 'pick' to 'unambiguous'."

---

## §6 Final campaign report

Assembled ONLY from the receipt manifests of W1–W3 (G1/G8). Structure: verdict paragraph →
three results tables → prediction scorecard (verbatim quotes + outcomes) → observation vs
speculation sections → full receipts manifest. Mark owns any public-facing rewrite; the lab
report is the internal source of truth. Drafts produced by Gemini are reviewed line-by-line
against receipts by the Architect before Mark sees them.
