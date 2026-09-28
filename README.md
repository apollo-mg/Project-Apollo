# Project Apollo

**A home lab for local LLM inference. Experiments are preregistered, every result has a receipt, and fixes go
upstream.**

The hardware is a desktop with an RX 9070 XT (RDNA4, 16 GB) and two servers holding six Tesla P100s. The questions
are the ones you hit running models locally on hardware like this:

- what a quantization actually costs;
- why the same model gives different answers on different GPUs;
- what a KV codec or a split mode does to the output and to the speed.

The answers are in `data/receipts/`.

## Start here

- [`data/receipts/INDEX.md`](data/receipts/INDEX.md) holds the findings, keyed by mechanism: determinism, KV-cache
  fidelity, speculative decoding, split modes, quant formats, MoE offload and hardware-specific behaviour. Grep it
  before designing an experiment.
- [`data/receipts/FAILURE_MODES.md`](data/receipts/FAILURE_MODES.md) lists the ways these measurements have gone
  wrong, and the control each one produced.
- [`STATUS.md`](STATUS.md) says what runs day to day and what is dormant.

**How results are reported.** Predictions are registered before the run and scored afterwards. Falsifications are
published next to confirmations. A claim that turns out wrong is corrected where it was made.

## Public artifacts

Things here that other people use, with the evidence behind each:

| what | where | status |
|---|---|---|
| **Slot save/restore checkpoint sidecar**: llama-server restored a saved session, then discarded it on the next request. With the sidecar, a parked 100K-token session resumes in about 4 s instead of a 12-minute re-prefill | [writeup](https://gist.github.com/apollo-mg/6defe7c0e3aba47727c758df03360b3e) | merged in [llama-cpp-turboquant #206](https://github.com/TheTom/llama-cpp-turboquant/pull/206) |
| **sm_60 FAST_FP16 carve-out**: Pascal P100s did quality-sensitive math in fp16 for years. A 3-line gate took median KLD from 0.0023 to 0.000001 at no speed cost | [`data/receipts/mtp-sm60/SUMMARY.md`](data/receipts/mtp-sm60/SUMMARY.md), [writeup](https://gist.github.com/apollo-mg/9218d50a209d70a85f033bf182657818) | merged in two forks ([llama-cpp-turboquant #212](https://github.com/TheTom/llama-cpp-turboquant/pull/212), [buun-llama-cpp #80](https://github.com/spiritbuun/buun-llama-cpp/pull/80)); upstream issue [ggml-org/llama.cpp #25593](https://github.com/ggml-org/llama.cpp/issues/25593) open |
| **Twin-Turbo chat-template fix**: restores tool calling for DavidAU's Qwen3.8-27B tune. The shipped template silently dropped `tool_calls` from history | [`templates/twin-turbo/`](templates/twin-turbo/) | adopted upstream by the model author ([discussion #10](https://huggingface.co/DavidAU/Qwen3.8-27B-TWIN-TURBO-Fable-Cold-Fusion-709-L-Uncensored-NM-DAU-NEO-MTP-GGUF/discussions/10)) |
| **D=256 quantized-KV collapse**: `q8_0`/`q4_0` with K *and* V quantized emits garbage on hardware without Turing-MMA or AMD-WMMA. Clean on RDNA4, same fork | [`data/receipts/kv-tensor-split/RESULT_RDNA4.md`](data/receipts/kv-tensor-split/RESULT_RDNA4.md) | reported to both forks |

---

## History: the orchestration layer (dormant since July 2026)

Apollo began as a local multi-agent orchestration layer. Most of it has not run since early July 2026, when the
work turned to measurement. [STATUS.md](STATUS.md) says which parts are verified live, and `CLAUDE.md` documents
the code. The pieces:

| component | where |
|---|---|
| SQLite message bus (WAL mode, atomic task claiming, tasks routed to nodes by context and precision requirements) | `message_bus_api.py`, `modules/message_bus.py` |
| Coordinator and WebSocket WebUI ("Glass Cockpit"), plus a terminal equivalent | a local checkout of [open-multi-agent](https://github.com/open-multi-agent/open-multi-agent); these two files were never published |
| Worker daemon for the remote P100 nodes | `worker_daemon.py` |
| Per-role agent profiles: endpoint, model, sampling, tools | `profiles.yaml` |
| Memory: hybrid BM25 + vector search, graph memory, daydream daemon | `modules/`, `vault/` |

Two things from that period still run: the wake-on-demand proxy that serves the daily-driver model, and a nightly
pass that collects open threads from the ledger into a morning brief.

---

## Acknowledgements & Credits
Project Apollo stands on the shoulders of giants. This Sovereign OS is made possible by the relentless innovation of the open-source AI community:
* **Garry Tan & GBrain:** For the architectural blueprint of the "Self-Wiring Memory Layer." Apollo's Daydream Regex Cascade (deterministic graph wiring) and Librarian Hybrid Search (Vector + BM25 + RRF) are direct implementations of the GBrain methodology, achieving zero-cost memory mapping without LLM overhead.
* **[open-multi-agent](https://github.com/open-multi-agent/open-multi-agent):** For the core TypeScript DAG orchestration and baseline agentic loops (MIT License).
* **@TheTom & AtomicChat:** For the bleeding-edge `llama-cpp-turboquant` and `atomic` forks that achieve extreme KV Cache compression, preventing VRAM meltdowns on consumer hardware.
  * *Academic Citation:* Zandieh et al., "TurboQuant: Extreme KV Cache Quantization" (arXiv:2504.19874, ICLR 2026).
* **spiritbuun & [buun-llama-cpp](https://github.com/spiritbuun/buun-llama-cpp):** For VBR (dynamic per-layer KV precision) and the build most of the receipts here run on.
* **SeaWolf-AI & the Qwen Team:** For the localized intelligence of the Qwen series and the Darwin-36B-Opus models (Apache 2.0).
* **Unsloth:** For their phenomenal imatrix and BF16 sources used in advanced model quantization.
* **Anthropic:** For pioneering the open Model Context Protocol (MCP) standard that powers Project Starbuck.

---
*Developed by Mark | AI Systems Architect | Indianapolis, IN*
