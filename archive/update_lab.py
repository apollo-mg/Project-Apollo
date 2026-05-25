import re

file_path = "/mnt/TG_2TB/Projects/Apollo/legacy_vault/MODEL_TEST_LAB.md"
with open(file_path, "r") as f:
    content = f.read()

# Add to the table
new_table_row = "| **Nemotron-Cascade-14B-Opus** | GGUF | 14B | **Logic/Code** | ✅ Tested | 8.4GB VRAM. ~48 TPS. Replaces DeepSeek-14B. |"
content = content.replace(
    "| **DeepSeek-V3-Distill-14B** | GGUF | 14B | **Logic/RAG** | ⏳ Idle Only | 9.5GB. 391W SIMD Saturation. Incredible logic. |",
    "| **DeepSeek-V3-Distill-14B** | GGUF | 14B | **Logic/RAG** | ❌ Deprecated | 9.5GB. Superseded by Nemotron-Cascade 14B. |\n" + new_table_row
)

# Add to the log section
new_log = """
### 6. Nemotron-Cascade-14B-Thinking-Claude-4.5-Opus-Distill
- **Source:** `TeichAI/Nemotron-Cascade-14B-Thinking-Claude-4.5-Opus-Distill.q4_k_m.gguf`
- **Date Added:** 2026-03-24
- **VRAM Footprint:** 8.4 GB (Full Offload)
- **Speed (t/s):** ~48.2 TPS
- **Intelligence:** Exceptional. Based on the Qwen 3 base, using Cascade RL, and distilled from Claude 4.5 Opus.
- **Verdict:** Immediate replacement for `DeepSeek-R1-14B`. Fits comfortably in 16GB VRAM while leaving ~8GB for context, and crushes previous 14B models in math and coding benchmarks.
"""

content = content + new_log

with open(file_path, "w") as f:
    f.write(content)
