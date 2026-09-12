# Prereg — EXL3 as a drop-in for the daily driver (EXL3 campaign, test 1)

**Written 2026-09-12 ~15:20, before any drop-in data exists.** This test covers ledger entries O2, O3, O4
and O5, plus a first O7 number, from `CAMPAIGN_EXL3.md`.

## Question

Does EXL3 still work when it is swapped into the daily driver's exact configuration? That configuration
is MTP drafting, the F16 mmproj, VBR KV at 262,144 context, and `-sm tensor`. And what is the decode speed
under the configuration a switch would actually face?

## Setup

- **Node:** `.73`, both P100s. The wake proxy is paused for the window, and a dead-man timer restores it.
  Orchestrated by `orchestrate_dropin.sh`; the driver is `exl3_dropin.py`.
- **Flags (`DAILY`):** `WP_START_CMD` as read from systemd at 15:05 on 2026-09-12. The shell wrapper, `-m`,
  `--host` and `--port` are removed; the server listens on 127.0.0.1:8190. The flags:
  - `--mmproj …/mmproj-F16.gguf -ngl 99 -c 262144`
  - `-ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto -np 1 -fit off -sm tensor -fa on`
  - `--spec-type draft-mtp --draft-max 3 --jinja --kv-unified`
  - `--chat-template-kwargs {"reasoning_effort":"medium"}`
  - `--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 0.0`
- **Binaries:**
  - **QUAL** is `~/buun-sm60-qual/build_sm60qual`, buun `9ae8f0f40` plus the e8m0 guard.
  - **DEPLOYED** is `~/buun-llama-cpp/build_sm60_head`, commit `c9c52d71`, which is what the proxy
    launches.
- **Weights:**
  - **EXL3** is `/mnt/HDD/exl3/Qwen3.8-27B-exl3-4.00bpw`, the snapshot qualified in
    `RESULT_EXL3_SM60_INFERENCE.md`.
  - **Q6K** is the daily driver's file (sha256 `562fbf76…`).

| arm | binary | weights | flags | why |
|---|---|---|---|---|
| **X** | QUAL | EXL3 | `DAILY` | the candidate |
| Xn | QUAL | EXL3 | `DAILY` minus `--spec-type`/`--draft-max` | EXL3's MTP gain |
| **Q** | QUAL | Q6K | `DAILY` | matched control: the same binary as X |
| Qn | QUAL | Q6K | `DAILY` minus MTP | GGUF's MTP gain |
| **D** | DEPLOYED | Q6K | `DAILY` | the daily driver as served |

**The run order is X, then Xn, Q, Qn, D.** A ladder runs **only if X fails to load**:
- **X-nomm:** `DAILY` minus `--mmproj`.
- **X-novbr:** the VBR flags replaced by `-ctk q8_0 -ctv q8_0`.
- **X-bare:** both changes, and no MTP.

Xn already covers "minus MTP". If a rung loads when X did not, that rung names the component that broke X.

## Stages, per arm

Each row is appended, flushed and fsynced as it is produced.

- **load:** readiness means the server answered a real chat completion, never `/health` alone. The row
  records `n_ctx`, `kv_bpv`, VRAM, and the server-log lines that mention MTP, nextn or drafting.
- **fact:** a one-word capital question, with thinking off and temperature 0. This is a coherence check.
- **vision:** for arms with `--mmproj`. The image is `vision_probe.png` (sha256 `92cd2850…`), the word
  KESTREL in black DejaVu Sans Bold on white. The prompt is *"What word is written in this image? Answer
  with the word only."*, with thinking off and temperature 0.
- **greedy:** 3 × 256 decoded tokens at temperature 0 and `top_k` 1, with `ignore_eos` and no prompt
  cache. The prompt is the inference receipt's speed prompt.
- **sampled:** 3 × 256 tokens at the server's own sampling (the daily driver's temp 1.0 / top-p 0.95 /
  top-k 20), with seeds 11, 12 and 13.
- **prefill:** a warm-up of the first 4,000 characters of wikitext-2 test, then **the scored run: the
  first 60,000 characters (about 15k tokens)**. `n_predict` is 1, with no prompt cache. `kv_bpv` is read
  back from `/slots` afterwards.

**Definitions:**
- **decode** is the median `predicted_per_second` over an arm's 3 reps.
- **acceptance** is Σ `draft_n_accepted` / Σ `draft_n` over those reps, from the server's own `timings`.

## Predictions

| id | prediction |
|---|---|
| P-D1 | X loads with the full daily-driver flag set |
| P-D2 | MTP engages on X: every greedy and sampled rep reports `draft_n` > 0 and `draft_n_accepted` > 0 |
| P-D3 | X's greedy acceptance is within 10 points of Q's |
| P-D4 | X's greedy decode is ≥ 0.80× Q's (same binary, both with MTP) |
| P-D5 | X's greedy decode **with** MTP beats Qn's greedy decode (Q6_K **without** MTP) |
| P-D6 | X reads the probe: its answer contains KESTREL (case-insensitive) |
| P-D7 | VBR is live on X: `n_ctx` is 262,144 and `kv_bpv` is reported below 16 at load |
| P-D8 | D's and Q's greedy decode are within 5% of each other, so the binary change is not a confound |
| P-D9 | X's scored prefill is ≥ 0.70× Q's |
| P-D10 | MTP gain on EXL3: X's greedy decode is ≥ 1.5× Xn's |

**Controls that gate predictions:**
- **P-D2 and P-D3** need Q to report `draft_n` > 0. If it does not, the MTP harness is broken and both are
  **VOID**.
- **P-D6** needs Q to read the probe. If it does not, the probe is invalid and P-D6 is **VOID**.
- **If X fails to load,** P-D2 through P-D7, P-D9 and P-D10 are **NOT TESTABLE**. The ladder's results are
  reported for attribution, and any follow-up is an amendment.

**The headline is descriptive, with no threshold:** X's sampled decode against D's. That is EXL3 with the
daily driver's flags against the daily driver as served. It replaces the charter's ~0.45× estimate.

## Declared in advance

- **Load time is not comparable.** EXL3 loads from `/mnt/HDD`, a spinning disk; Q6K loads from NVMe (O10).
- **VBR sizes itself.** Under `--vbr-vram auto`, VBR adapts to free VRAM. EXL3 leaves about 8 GB more
  free, so X's `kv_bpv` may differ from Q's. Speed is compared at each arm's own automatic setting, as a
  deployment would run, and both `kv_bpv` values are reported.
- **Sampled reps measure speed, not quality.** They are seed-fixed but not expected to match across arms,
  because the weights differ. They measure speed and acceptance under the served sampling.
- **This is a speed estimate, not a distribution:** one prompt, 256 tokens, 3 reps.
- **The ledger may miss a run.** The dev-diary ledger calls the daily driver hourly at :05, and the
  window is timed to finish before 16:05. If it overruns, that ledger run fails, and the receipt says so.

**Scorer:** `tools/score_exl3_dropin.py`, committed with this prereg.
