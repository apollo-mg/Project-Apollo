# Lab Spec — Qwen-AgentWorld-35B-A3B bring-up & characterization on .73

**Owner:** Antigravity (Gemini quota). **Author of spec:** Claude (Opus), 2026-07-23. **Box:** `.73` (ai-p100-sli).
**Goal:** stand up Qwen-AgentWorld-35B-A3B on .73 and determine, with receipts, whether it is viable as a
**simulated-environment engine** for agentic-eval blind-spot discovery — BEFORE building any benchmark system on top.

## What this model is (read before prompting it)
AgentWorld is a **language world model**, NOT an agent. Given (domain system prompt + agent action + interaction
history) it **predicts the next environment observation**. One model covers 7 domains: MCP (tool calling), Search,
Terminal, SWE, Android, Web, OS. It is a **reasoning model** — thinking-on by default, emits `<think>...</think>`;
in the OpenAI-compat API the think trace lands in `reasoning_content` and the predicted observation in `content`.
**Every probe must read BOTH fields** (same failure mode we hit on Puzzle/Laguna: an empty `content` with a full
`reasoning_content` is a budget/format artifact, not a model failure). Arch: `Qwen3_5MoeForConditionalGeneration`,
40 layers, `full_attention_interval=4` (10 full-attn layers + 30 gated-deltanet linear layers), 2 KV heads,
head_dim 256, 256 experts / 8 active (~3B active / 35B total), max_position_embeddings 262144.
Recommended sampling: **temp 0.6, top_p 0.95, top_k 20**; card advises **≥128K context** for multi-turn envs.

## Hardware & build (verified 2026-07-23 — do not re-derive, but confirm still true)
- `.73` = 2× Tesla P100-PCIE-16GB (sm_60, CUDA 12.4), **32GB VRAM total**, **16GB system RAM** (cold HDD model
  loads are slow — budget ~10 min; this bit us before via health timeouts), **520GB free** on `/`, PHB topology
  (GPU0↔1 same host bridge → tensor-split is viable here, unlike .194's cross-socket quad). GPUs boot **150W cap**,
  idle 405MHz (record actual clock/power in every receipt — do NOT assume autoboost).
- Build: **`/home/mark/buun_vbr/build/bin/llama-server` v10440 (b88daada9)**. Arch support CONFIRMED by source:
  `src/models/qwen35moe.cpp`, `src/models/qwen3next.cpp`, GDN kernels, and commit *"tap: bake qwen35moe (35B-A3B)
  KV means — the fleet's biggest untapped win"* + *"fix: tensor split mode for GDN hybrid models"*. This model class
  is a first-class citizen on this fork; turboquant KV (buun's VMEAN tap) is tuned for exactly it.

## KV / context budget (verified from config.json — why full context fits)
Only 10 of 40 layers cache KV (the rest are fixed-state GDN linear attention). KV/token fp16 =
2·10·2·256·2 ≈ **20 KB/tok** → **~5 GB fp16 at the full 262k**, **~1–1.5 GB under turboquant**. So even at
UD-Q4_K_XL (22.3GB weights) + 5GB fp16 KV = ~27GB, full 262k fits in 32GB; with turboquant KV there is ample room
for Q5 (26.5GB) or Q6 (31.8GB). **Context is NOT the constraint on this box** (correcting an earlier wrong estimate).

---

## GATE 1 — Bring-up (fail-fast on arch/serving)
**Quant:** arch is confirmed, so **skip the throwaway tiny quant** and pull the one we'd characterize with:
**`Qwen-AgentWorld-35B-A3B-UD-Q4_K_XL.gguf` (22.3GB)** from `unsloth/Qwen-AgentWorld-35B-A3B-GGUF`
(`https://huggingface.co/unsloth/Qwen-AgentWorld-35B-A3B-GGUF`). Download directly to `.73:~/AI/Models/AgentWorld/`
(has internet + 520GB free); if no direct egress, stage on control-plane and scp. (Ultra-cautious fallback only:
UD-IQ2_XXS 11.5GB as a pure load-test — but for a *world model*, Q2 is too degraded to judge simulation fidelity.)

**Launch** (start conservative; A/B refinements in Gate 3):
```
~/buun_vbr/build/bin/llama-server \
  -m ~/AI/Models/AgentWorld/Qwen-AgentWorld-35B-A3B-UD-Q4_K_XL.gguf \
  -ngl 99 -sm layer -ts 1,1 -ub 64 -c 32768 -np 1 \
  --host 0.0.0.0 --port 8082 2>&1 | tee ~/agentworld/bringup_server.log
```
Notes: `-ub` small (P100 + MoE); start `-sm layer` (safe) — tensor-split is available (GDN fix) and A/B'd in Gate 3.
Do NOT assume `-fa` — the known-good for the sibling Puzzle omitted it; try WITHOUT first, then WITH, record which
loads and whether numerics differ. turboquant KV (`-ctk turbo8 -ctv turbo3`) is OPTIONAL here — first prove fp16
loads, then enable turbo and confirm the qwen35moe VMEAN tap arms cleanly.

**PASS:** loads with no arch/metadata error, `/health` → 200, `/props` shows the expected `n_ctx`. **Record:** exact
cmdline, build string, per-card VRAM (`nvidia-smi`), the server-log KV/state buffer-size line, and GPU clock+power.
**FAIL:** capture the arch/load error **verbatim** and STOP — do not proceed to build anything; escalate (may need a
newer buun pull). This is the Puzzle discipline: never build on a model that doesn't cleanly load.

## GATE 2 — Simulation smoke (is it a coherent world model, not a chatbot?)
Use the **domain system prompts** from the model's GitHub `prompts/` directory (linked from the HF card) — do not
invent them. Minimum: **Terminal** + one of {MCP tool-calling, Search}. Example (Terminal):
- system: `"You are a language world model simulating a Linux terminal environment. Given the user's command, predict the terminal output."`
- user: `"Action: execute_bash\nCommand: ls -la /home/user/project/"`
- sampling: temp 0.6, top_p 0.95, top_k 20, max_tokens 2048.
**Read BOTH `content` and `reasoning_content`.** PASS = a plausible, on-format simulated observation (a believable
`ls` listing), NOT a chat reply, refusal, or degenerate loop. Save full request/response transcripts as receipts.

## GATE 3 — Characterize on .73 (the publishable finding)
1. **Context ceiling:** raise `-c` toward 262144 (with turboquant KV) and record the max that loads + serves on 32GB.
2. **Speed:** decode t/s at shallow (d≈2k) and deep (d≈128k) context. **A/B `-sm layer` vs `-sm tensor`** — .73 got
   +57% decode on tensor for Qwen3.6-27B; does the GDN hybrid replicate it? (Receipt each leg with clock/power.)
3. **Domain coverage:** which of the 7 domains produce coherent simulations at Q4.
4. **Quant fidelity (if time):** spot-check Q4 vs Q5/Q6 on the same simulation prompts — a world model's value is
   realism, so do not assume Q2/Q4 is "good enough" without looking.

## Standing constraints (non-negotiable)
sm_60/P100; `-ub` small; **record GPU clock+power in every receipt** (150W cap, not autoboost); do **NOT** format
`/mnt/HDD`; **read every third-party file before executing it**; do **NOT** modify any Starbuck files; treat this model
as a reasoning model (handle `<think>`/`reasoning_content`) in all probes; sampling temp 0.6/top_p 0.95/top_k 20.
Receipts under `.73:~/agentworld/`. Do not disturb the `.194` Puzzle HumanEval+ run (different box, shared conventions).

## The oracle problem (design note for the eventual benchmark — NOT gates 1–3)
If a benchmark uses AgentWorld to simulate the environment, AgentWorld cannot also be the sole judge of task success
(circular). Any benchmark built on it needs **independent ground-truth success criteria**. Resolve this in the design
phase before writing the harness.

## Deliverable
A bring-up report (receipts) + explicit **go/no-go**: is AgentWorld-as-simulator viable on .73, at what context/quant/
speed, and which domains hold up — then Mark + agents decide whether the full benchmark system is worth building.
Log a short entry under `CHANGELOG.md` `[Unreleased]` when done.
