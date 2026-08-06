# VBR Day-One Validation Protocol (P100 / Pascal)

**Target:** buun's VBR launch (spiritbuun/buun-llama-cpp master, pushed 2026-07-10 ~16:18Z).
**Why us:** Pascal sm_60 is NOT in buun's validated set (3090 / gfx1151 / gfx1201 only). We have his
eval pack, pre-built KLD bases on .194 (cross-build f16 anchor VERIFIED exact-zero 2026-07-10), and
two P100 machines. Nobody else can produce an honest Pascal validation this week.

**The two traps every naive reviewer will fall into (we must not):**
1. **Pressure trap.** VBR starts at f16 and only degrades under real VRAM pressure. A KLD/PPL cell
   with `-ct vbr` on an unpressured rig scores as f16 and measures NOTHING. Every quality cell must
   pin the regime via `--vbr-budget <tier|number>` (static mix) or `--vbr-vram <SIZE>`.
2. **l64 trap** (buun's own INSIGHTS §5). Positional/VBR-style schemes are judged wrong by full-window
   KLD. Quality verdicts need BOTH full-window and `TURBO_SCORE_LAST_K=64` passes.

**Standing rules:** R-gate applies — every claim in the writeup cites a receipt file. Causal verbs
need an ablation. Read every output before trusting it (coherence gate first, INSIGHTS rule 1).
Do NOT touch `~/buun_tree` or the running ladder on .194. Never build/copy onto .73's root NVMe
(99% full) — everything goes to `/mnt/HDD` (342G free).

---

## Phase 0 — Provision (build on .194, run on .73)

.73 CANNOT compile this: its toolkit is CUDA 13.3 (sm_60 support removed in 13.0) and its root disk
is full. .194 has CUDA 12.4 (sm_60 OK — it built buun_tree).

```bash
# On .194 — safe alongside the ladder (CPU-only work; cap -j so cells aren't starved)
cd /home/mark
git clone https://github.com/spiritbuun/buun-llama-cpp buun_vbr   # keep .git => real build_sha stamps
cd buun_vbr
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 -DLLAMA_CURL=OFF
cmake --build build --target llama-server llama-perplexity llama-bench -j 12
```

Receipt 0a: `./build/bin/llama-server --version` → must print a real SHA (no more `build: unknown (0)`).
Record the SHA; it must match spiritbuun/master HEAD.

```bash
# Ship to .73 (HDD only). Note: buun's build makes shared libs (libllama-*-impl.so) —
# copy the whole bin dir and always run with LD_LIBRARY_PATH pointing at it.
ssh mark@10.0.0.73 'mkdir -p /mnt/HDD/vbr/bin /mnt/HDD/models /mnt/HDD/data'
scp -r /home/mark/buun_vbr/build/bin/* mark@10.0.0.73:/mnt/HDD/vbr/bin/
scp "/home/mark/AI/Models/Qwen 3.6/27B/Qwopus/Qwopus/Coder/Qwopus3.6-27B-Coder-heretic-Q6_K.gguf" \
    mark@10.0.0.73:/mnt/HDD/models/
scp /home/mark/wikitext-2-raw/wiki.test.raw mark@10.0.0.73:/mnt/HDD/data/
```

**GATE 0 (driver compat, 30s):** binaries are cudart-12.4; .73's driver is 535 (12.2-era).
```bash
ssh mark@10.0.0.73 'LD_LIBRARY_PATH=/mnt/HDD/vbr/bin /mnt/HDD/vbr/bin/llama-server --list-devices'
```
- Both P100s listed → proceed.
- CUDA init error / insufficient driver → STOP; fix = upgrade .73 to the 580 branch (.194 runs its
  P100s on 580.159, so 580+Pascal is proven). Mark's call (sudo + reboot). Do not "work around" this.

**GATE 0 OUTCOME (2026-07-10): FAILED — earlier than expected, at the OS layer.** Loader abort on
.73: `GLIBC_2.43 not found` / `OPENSSL_3.3.0 not found` (.194's OS is newer than .73's Ubuntu 24.04,
glibc 2.39). Gemini stopped per protocol; no workaround attempted. **DECISION: .73 is OFF the
critical path.** Phase A runs on .194 after the ladder completes, using `--vbr-vram` (e.g. `3G`) to
force the pressure regime the 2-GPU box would have produced naturally. Only deferred loss:
"auto-budget derives sanely on a constrained rig."
.73 proper fix, when worth an afternoon: (1) remove CUDA 13.3 to free the 99%-full root disk,
(2) CUDA 12.6 runfile → `--toolkitpath=/mnt/HDD/cuda-12.6`, `TMPDIR=/mnt/HDD/tmp` (12.6 supports
Ubuntu 24.04/gcc-13 and still targets sm_60), (3) driver 580 while sudo'd (Pascal-proven on .194),
(4) build natively on .73. Hygiene rule: shipped libs (e.g. libnccl) live ONLY in /mnt/HDD/vbr/bin
under LD_LIBRARY_PATH — never copy libraries into /lib or /usr on the target box.
Model on .73 verified byte-identical to .194's canonical Qwopus (22,082,528,736 bytes,
/mnt/HDD/mark/) — valid whenever .73 comes back into play.

**GATE 0 RE-RUN (2026-07-11): PASSED.** Mark reinstalled .73 with Kubuntu 26.04 (glibc 2.43 — the
exact version the loader wanted) on a spare 640GB HDD; old 465GB data drive survived untouched and
is remounted at /mnt/HDD (fstab UUID entry added, Qwopus re-verified byte-identical). Driver
580.159.03 via distro `nvidia-driver-580` (same version as .194), both P100s enumerate.
CUDA 12.4 runtime libs (libcudart/libcublas/libcublasLt) shipped from .194 into /mnt/HDD/vbr/bin
per the hygiene rule (app-local only, LD_LIBRARY_PATH). The original Gate 0 command
(`llama-server --list-devices` on the .194-built binary) now lists both devices. **Consequence:
build-on-.194, run-on-.73 works with no toolkit on .73.** Also: 32GB Optane NVMe repurposed as
/mnt/optane with a 16GB swapfile at swap priority 100 (installer's 512MB HDD swapfile demoted to
fallback — priority order verified post-reboot).

---

## Phase A — Prelim on .73 (functional; the "does it even work on Pascal" report)

Env for all runs: `BIN=/mnt/HDD/vbr/bin; export LD_LIBRARY_PATH=$BIN`
Model: `M=/mnt/HDD/models/Qwopus3.6-27B-Coder-heretic-Q6_K.gguf`
2×P100 = 32G; weights ~22G split ⇒ ~4-5G/GPU for KV+compute ⇒ genuine budget pressure (the point).

**A1 — Coherence gate (before ANY metric).**
```bash
$BIN/llama-server -m "$M" -ngl 99 -ct vbr -v --port 8090 2>&1 | tee /mnt/HDD/vbr/logs/a1_serve.log
# then: one /v1/chat/completions request, ~500 tokens. READ THE OUTPUT. Broken kernels can look
# like "mild degradation" in metrics while being word salad (INSIGHTS rule 1).
```
Receipt: the generated paragraph + log. Also grep the log now for the arch line and FA status
(VBR force-enables FA; confirm the P100 FA path engaged, no silent CPU fallback).

**A2 — Does dynamic mode ENGAGE on Pascal? (VMM check — a real day-one finding either way)**
Dynamic VBR rides the VMM pool (`vbr-vmm.cu`, cuMemMap); code "falls back to plain cudaMalloc when
the device has no VMM support." If Pascal lacks VMM, dynamic mode may be degraded/unavailable —
that is a headline finding, not a failure of ours.
Receipt: grep A1/A3 logs for VMM pool init vs fallback lines; `nvidia-smi` samples during fill.

**A3 — Degrade cascade fires, in price order.**
```bash
$BIN/llama-server -m "$M" -ngl 99 -ct vbr -v --vbr-vram 3G --port 8090 2>&1 | tee /mnt/HDD/vbr/logs/a3_degrade.log
# feed a long prompt (wiki.test.raw chunks) via /completion until degrades fire
grep "VBR degrade" /mnt/HDD/vbr/logs/a3_degrade.log
```
Check: steps go one (layer, side) at a time, monotonically down the ladder
(f16→turbo8→turbo4→turbo3_tcq→turbo2_tcq→turbo1_tcq). Qwopus = qwen35 arch (16 attn layers): README
says 160 steps f16→floor. Does Qwopus use the baked qwen35 price order or the "generic cross-model
order"? The log should say — record which. Receipt: the degrade line sequence.

**A4 — Budget adherence + clean stop.** With `--vbr-vram 3G`: VRAM for KV must stay ≤ budget
(nvidia-smi receipts), no OOM at deep fill, and when context fills "generation stops cleanly" —
verify no crash/garbage. Receipt: nvidia-smi timeline + server log tail.

**A5 — Save/restore contract.** Dynamic mode: slot save/restore should be DISABLED (attempt
`/slots/0?action=save` → expect a clean refusal, not a crash). Static mode (`--vbr-budget t4`):
save/restore should work. Hybrid-model context checkpoints should remain enabled in both (README
carve-out). Receipt: HTTP responses + log lines. NOTE for Apollo production: dynamic VBR is
incompatible with our park-and-resume (~720×) workflow until buun's tier-aware save-restore lands.

**A6 — Throughput on Pascal.**
```bash
$BIN/llama-bench -m "$M" -ngl 99 -fa 1 -ctk q8_0 -ctv q8_0 -p 8192 -n 32 -d 8192
$BIN/llama-bench -m "$M" -ngl 99 -fa 1 -ctk turbo4 -ctv turbo4 -p 8192 -n 32 -d 8192
$BIN/llama-bench -m "$M" -ngl 99 -fa 1 -ctk turbo3_tcq -ctv turbo3_tcq -p 8192 -n 32 -d 8192
# label layer honestly: this is llama-bench raw, not server wall-clock
```
(If llama-bench lacks a vbr row type, bench the fixed tiers and measure vbr via server timings.)
Receipt: bench tables. Context: on 4×P100 buun's tcq prefill was 2.077× Tom's turbo — expect TCQ to
be fast here; what's unknown is the per-tier spread on 2 GPUs.

---

## Phase B — Metrology on .194 (AFTER the ladder run is DONE — check first)

The question VBR actually poses: **at matched bytes, does per-layer price-order allocation beat a
uniform tier?** (The bathtub/naivepos design, layer axis instead of position axis.)

Prereq: ladder complete; bases valid for buun-lineage builds (f16 anchor = exact zero, verified).
Run with the SAME buun_vbr build (fresh clone above), new run_dir, floor rides.

- Arm 1 (uniform): `-ctk turbo4 -ctv turbo4` (4.124 bpw — ladder already has these cells).
- Arm 2 (VBR static mix at matched bytes): `-ct vbr --vbr-budget 4.124` (a NUMBER = fixed static
  mix per price order, no runtime degrades). Confirm actual allocation from the log / KV MiB —
  the bpw probe reads f16-at-start for dynamic vbr, so for VBR cells trust the server/perplexity
  log tier map, not the probe.
- Repeat at the 3.25 rung: uniform `turbo3_tcq` vs `--vbr-budget 3.249`.
- Judge: median KLD @2k/8k/16k, full-window AND `TURBO_SCORE_LAST_K=64` (l64) passes. q8_0 floor
  rides. Same bases (`/home/mark/turbo-logits-kld`), no new disk.
- Honest expectation: if the mix at 4.124 lands ~turbo4 ± floor, VBR's value is the *dynamics*
  (A3/A4), not static allocation — that's a fine finding. If the mix beats uniform at matched
  bytes on l64, that's buun's central claim confirmed on Pascal.

## Deliverable
`data/Apollo Docs/vbr_pascal_day_one.md` — findings with receipt paths, O/I/U discipline, and the
per-claim falsifier. Cross-reference buun's published 3090 numbers (turbo3_tcq median 0.00163 @16k)
against our ladder's P100 cell — replication or divergence, either is reportable.
