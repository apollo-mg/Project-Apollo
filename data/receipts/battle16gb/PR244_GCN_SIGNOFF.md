# GCN Vulkan sign-off: the turboquant rebase preserves wave64 correctness — 21/21 healthy, and fully deterministic at K=3

`.76` bench rig — RX 580 8 GB (Polaris10/GCN4, **subgroup size 64**), RADV Mesa 26.1.6,
CachyOS live USB, Pentium G3258, 7 GB RAM. Model Crow-9B IQ4_XS.
Date 2026-08-02. Requested by TheTom in `TheTom/llama-cpp-turboquant#244` as the GCN Vulkan
post-adoption assurance.

**Build under test:** adopted head **`c19884fb4`**, `version: 10249` — i.e. giveen's
`418cbf49b` + Tom's `supports_op` reconstruction `28c68fe74`, which is what
`feature/turboquant-kv-cache` now points at. Compiled with `GGML_AVX/AVX2/F16C/FMA/BMI2=OFF`,
`-march=x86-64-v2`, `.note.gnu.property` stripped for the G3258.

**Reference:** build **9981** @ `11a8377bd` (`TURBO3_241_WAVE64_FIX_CONFIRMED.md`), the
pre-rebase head now tagged `pre-rebase-2026-08-02`.

Predictions logged pre-run: `PREDICTIONS_pr244_turbo3.md`.

## Result — K=3, 7 cells, 21 runs, zero failures

| cell | gzip (all 3 reps) | band | sha (all 3 reps) | 9981 ref |
|---|---|---|---|---|
| kturbo4_vturbo3 | 0.4961 | healthy | `5afcafda0c5d` | `b031d9c337e8` / 0.4866 |
| kf16_vf16 | 0.5097 | healthy | `ad9dd4fa776f` | **identical** / 0.5097 |
| kturbo4_vturbo4 | 0.5101 | healthy | `4a86d5f4c3f3` | `9e33a09474a1` / 0.5024 |
| kturbo4_vturbo2 | 0.5021 | healthy | `0b3b5c4235d5` | **identical** / 0.5021 |
| kturbo3_vturbo3 | 0.5149 | healthy | `2cf82bbbff4a` | `4cb388a93d6d` / 0.5152 |
| kf16_vturbo3 | 0.5251 | healthy | `1dc38ed16d50` | `169b27a7251c` / **0.5251** |
| kturbo3_vf16 | 0.5206 | healthy | `6f6426953a0a` | `e89131fbe39d` / 0.5199 |

**All 21 runs in the healthy band (≥0.45). Nothing marginal, nothing corrupt.** For scale, the
wave64 ballot bug this rig was built to catch produced **0.175–0.347** on turbo3 cells.

The three **turbo3-V** cells — the ones the wave64 `signs`-packing bug corrupted — land at
0.4961, 0.5149 and 0.5251 against pre-rebase references of 0.4866, 0.5152 and 0.5251. The
`#243` fix is intact in the rebase.

## Two results worth separating

**1. Determinism.** Every cell produced the **same SHA in all three reps** — 7/7 self-consistent,
21 runs, zero variation. Timings were tight too (411–455 s, ±1%).

**2. Byte-identity to pre-rebase.** 2 of 7 cells (`kf16_vf16`, `kturbo4_vturbo2`) are
byte-identical to the 9981 references. The other 5 diverge in bytes while staying in band —
expected across 268 upstream builds of sampling/graph changes, and **not** a regression
signal. `kf16_vturbo3` is a nice intermediate case: gzip matches the reference to four
decimals (0.5251) while the SHA differs.

## Prediction scoring — 3 confirmed, 1 falsified, 1 partial

| id | claim | conf | outcome |
|---|---|---|---|
| P-R1 | all 3 turbo3-V cells ≥ 0.45 in all 3 reps | 0.85 | **CONFIRMED** |
| P-R2 | no cell in any rep < 0.40 | 0.80 | **CONFIRMED** — min 0.4961 |
| P-R3 | outputs **not** byte-identical to 9981 refs | 0.85 | **PARTIAL** — 5/7 diverge, 2/7 identical |
| P-R4 | f16/f16 control is bistable across reps (≥2 SHAs) | 0.55 | **FALSIFIED** — 1 SHA, 3/3 |
| P-R5 | turbo2/turbo4 cells self-consistent across reps | 0.45 | **CONFIRMED** — and so was every other cell |

### P-R4 is the interesting failure

`F16_CONTROL_BISTABLE.md` established that the f16 control on this exact rig produced **two
distinct output states** across runs with cell order held fixed — which is why this matrix was
specified at K=3 rather than K=1. It did not reproduce. The control was perfectly stable here,
and so was every other cell.

Something changed between those runs and this one, and I can name a candidate but not prove
it: **this run wrote all logs to `$HOME` (RAM overlay); every earlier run on this rig wrote
them to the exfat USB mount during generation.** That same change is what stopped the matrix
wedging the GPU (see `PR244_POLARIS_TRIAGE.md`). If FUSE write stalls were perturbing
execution timing, and the bistability was timing-dependent, removing the stalls would remove
the bistability — consistent with the prior finding that these outputs are
*execution-order dependent, not time dependent*.

**That is a hypothesis with a plausible mechanism, not a result.** Testing it means re-running
the matrix with logs back on the USB and seeing whether bistability returns — a deliberate
re-break, not done here. Until then: **do not treat this rig as deterministic in general.**
K=3 remains the right instrument; it happened to agree with itself this time.

P-R5 was set below even odds (0.45) reasoning that if the f16 control was bistable, whatever
caused it might touch turbo2/turbo4 too. It confirmed — because *nothing* was bistable.

## Limits

- One GPU (Polaris10/GCN4), one driver (RADV 26.1.6), one model (Crow-9B IQ4_XS), one prompt,
  temp 0, 500 tokens.
- **gzip ratio is a degeneracy gate, not a fidelity metric.** "Healthy band" means "not
  degenerate"; it does not establish that turbo KV is numerically lossless. A subtle
  accuracy regression that keeps output fluent would pass this test. KLD against an f16
  reference is the instrument for that, and was not run here.
- Byte-divergence from 9981 on 5 cells is **unexplained in detail** — attributed to 268
  builds of upstream drift, not investigated commit-by-commit.
- `max_tokens` 500 was held fixed because the healthy/corrupt bands were calibrated at that
  length; 80-token triage runs score ~0.73 while perfectly healthy, so the bands are
  length-specific.
- Determinism here is 3 draws on one afternoon, on a rig with a documented history of
  bistability. See P-R4.

## Provenance

- `.76:~/adopted_mx/` — master log + `rep{1,2,3}/{server_*.log,resp_*.json}`; copied to
  `/mnt/usb/adopted_mx/` after all servers stopped
- Local: `pr244_artifacts/adopted_c19884fb4_matrix_k3.log`, `pr244_artifacts/adopted_rep1/`
- Script `~/turbo3_adopted.sh`; local copy `scratchpad/turbo3_adopted.sh`
- Binaries `/mnt/usb/tqbin_adopted` (10249 @ `c19884fb4`), reference `/mnt/usb/tqbin_w64`
  (9981 @ `11a8377bd`)
- Partial run on PR-head content (`c86e57d82` + local compile fixes, superseded):
  `pr244_artifacts/prhead_c86e57d82_rep1_partial.log` — 5 cells, all healthy, same two cells
  byte-identical
