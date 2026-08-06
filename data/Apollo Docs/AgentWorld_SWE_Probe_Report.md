# Research Note: AgentWorld-35B-A3B SWE Domain Probe (Git & Setuptools)

**Date:** 2026-07-23
**Node:** `.73` (ai-p100-sli) — 2× Tesla P100 16GB
**Model:** `Qwen-AgentWorld-35B-A3B-UD-Q4_K_XL.gguf`

## Objective
Following the Terminal depth probe, which suggested AgentWorld suffers from an "implicit artifact omission" blind spot (e.g., missing Python's `__pycache__`), we branched into the Software Engineering (SWE) domain. The goal was to test this hypothesis by running standard SWE commands (`git init`, `git commit`, `python3 setup.py build`) to see if the simulator would fail to generate implicit objects (e.g., `.git/objects/`, `build/`).

## Finding 1: The Hypothesis is Refuted (Flawless Git Internal Modeling)
The "implicit artifact omission" hypothesis is DEAD. AgentWorld models Git internals with shocking, flawless precision.

*   **`git init` and `.git/` Skeleton:** Upon running `git init`, a subsequent `ls -la .git/` correctly yielded the entire implicit repository skeleton (`HEAD`, `config`, `description`, `hooks/`, `info/`, `objects/`, `refs/`), matching ground truth exactly.
*   **`git commit` and `.git/objects/`:** We added a file and ran `git commit`. AgentWorld predicted the commit output perfectly (assigning it a fake hash `8f3a9c2`). When we ran `ls -la .git/objects/`, AgentWorld **perfectly simulated the implicit creation of three Git objects** (the blob, tree, and commit). It correctly rendered three new directories (`8f`, `c4`, `e8`) alongside the default `info/` and `pack/`, with `8f` mathematically corresponding to its own simulated commit hash!

## Finding 2: Over-Prediction in Build Artifacts
We simulated a Python `setuptools` build sequence:
`echo 'from setuptools import setup, find_packages; setup(name="demo", packages=find_packages())' > setup.py`
followed by `python3 setup.py build`.

*   **Ground Truth:** Because there were no subdirectories with `__init__.py`, `find_packages()` returned empty. Real `setuptools` executed but *did not* create a `build/` directory.
*   **AgentWorld:** AgentWorld assumed the build was standard and **hallucinated the existence of a `build/` directory** containing a `lib/` folder. 

**Conclusion on Fidelity:** AgentWorld does not ignore implicit tool artifacts. In fact, its prior on standard SWE tool behavior is so strong that it models internal object trees (`.git/objects`) perfectly, and will even *over-predict* build folders (`build/`) when a real tool would silently abort due to empty configuration.

## Finding 3: Compute Cost Compounds Massively in SWE
While fidelity is incredibly high, the token cost to render these complex internal states is brutal.
*   `git init`: **6,501** reasoning tokens
*   `ls -la .git/`: **7,409** reasoning tokens
*   `git commit`: **2,904** reasoning tokens
*   `ls -la .git/objects/`: **9,715** reasoning tokens
*   `python3 setup.py build`: **6,718** reasoning tokens
*   `ls -la` (at root): **9,646** reasoning tokens

**The SWE Bound:** AgentWorld is a shockingly capable SWE oracle, capable of modeling Git's mathematical internals. However, any sequence requiring it to inspect its own accumulated SWE state (`ls -la .git/objects/`) triggers massive ~10,000 token reasoning blocks. A 20-turn SWE session that repeatedly lists directories will rapidly exhaust even the 262k context window and take extensive wall-clock time to compute.
