# 🧪 APOLLO TRAINING LAB: Agentic Learning PoC

Welcome to the Training Lab. This is where we bridge the gap between "consuming" AI and "creating" it by fine-tuning models on your own sovereign hardware (RX 9070 XT).

## 🧬 The Workflow: "The Group of Friends" (GRPO)

Traditional training requires a massive dataset of "Correct" answers. **GRPO (Group Relative Policy Optimization)** changes the game by using a "Group of Friends" approach:

1.  **The Generation:** The "Student" model (e.g., Qwen 1.5B) generates a group of different answers to the same prompt.
2.  **The Comparison:** We calculate the **average reward** for the entire group.
3.  **The Advantage:** The model is rewarded for answers that are **better than the group average** and penalized for those that are worse.
4.  **The Reward Function:** We define "what is good" (e.g., no corporate filler, technical accuracy, mentioning ROCm).

## 🏗️ Getting Started (Proof of Concept)

### 1. Synthetic Data Generation
If you don't have enough data, use your "Architect" models (80B Coder or GLM-4.7) to generate a high-quality dataset of engineering notes.
```bash
python3 training_lab/scripts/synthetic_gen.py
```

### 2. Visualize GRPO Logic
Run the PoC script to see how the "Reward Function" scores different model outputs against each other.
```bash
python3 training_lab/scripts/grpo_poc.py
```

## 🏎️ SOTA Stack for RDNA 4 (GFX1201)

To move from PoC to actual training, you'll need the following installed:
*   **PyTorch (ROCm 7.2 Nightly):** For native FP8 support.
*   **Unsloth:** For extreme VRAM efficiency (Fine-tune 30B models on 16GB).
*   **AITER:** To accelerate the math kernels during the training pass.

---
*Status: Phase 9 (Sentinel) Preparation*
