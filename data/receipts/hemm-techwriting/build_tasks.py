#!/usr/bin/env python3
"""Build tasks.json for PREREG_HEMM_TECHWRITING.md from real repo material (sources are frozen into
the JSON so the test does not drift if the receipts are edited later)."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R = ROOT / "data/receipts"
sys.path.insert(0, str(ROOT / "tools"))


def section(rel, start, end=None, maxc=3500):
    t = (R / rel).read_text() if not rel.startswith("/") else Path(rel).read_text()
    i = t.index(start)
    j = t.index(end, i + len(start)) if end else len(t)
    return t[i:j].strip()[:maxc]


def func_src(path, name):
    t = (ROOT / path).read_text()
    i = t.index(f"def {name}(")
    m = re.search(r"\n(?=def |class |if __name__)", t[i + 5:])
    return t[i:i + 5 + m.start()].rstrip() if m else t[i:].rstrip()


T = []
def add(tid, kind, prompt, source=None, facts=None, misconceptions=None):
    T.append({"id": tid, "kind": kind, "prompt": prompt, "source": source,
              "key_facts": facts or [], "misconceptions": misconceptions or []})

SUM = ("Write a summary of the source below for a technical blog audience (engineers who run local "
       "LLMs but did not see this experiment). About 150-200 words, plain prose, no headings. Use only "
       "facts that are in the source.\n\nSOURCE:\n{src}")
add("S1-reap", "summary", SUM, section("reap-flashnext/RESULT_REAP_FLASHNEXT.md", "## Results", "## What it means"))
add("S2-kvdepth", "summary", SUM, section("kv-depth/RESULT_KV_DEPTH_MATCHED_ALLOCATION.md", "# Frozen VBR", "## The allocation frontier"))
add("S3-mtp", "summary", SUM, section("mtp-agentic/RESULT_MTP_AGENTIC.md", "## Primary result", "## What the smoke established"))
add("S4-noisefloor", "summary", SUM, section("argus-v2/RESULT_NOISE_FLOOR.md", "# Result", "## Predictions, scored"))

BUG = ("Write a GitHub issue for the project's maintainer from the facts below. Include a title, a short "
       "summary, reproduction steps, observed vs expected behaviour, and anything ruled out. Do not add "
       "facts that are not listed.\n\nFACTS:\n{src}")
add("B1-vbr-sticky", "bug_report", BUG, """- Project: buun-llama-cpp, commit 38ada0e1b, ROCm build, RX 9070 XT (also the desktop display GPU)
- Command: HIP_VISIBLE_DEVICES=0 llama-perplexity -m Qwen_Qwen3.5-9B-Q8_0.gguf -f wiki.test.raw -ngl 99 -fa on -c 32768 -b 512 -ub 512 -v --chunks 2 -ctk vbr -ctv vbr --vbr-vram 2048M
- Chunk 1: first VBR degrade at 25,088 cells; end of chunk 1 log: "projected 552.00 / budget 2048.00 MiB (mapped 574.50) at 32768 cells"
- Then the log says "VBR full reset: cache empty -- 15 tensors back at their entry tier" (the model has 16 KV tensors: 8 layers x K/V)
- In the same millisecond, degrades #1..#N fire at 0 cells and walk every tensor to turbo1_tcq before chunk 2 has any tokens
- Free VRAM sampled every 0.5 s never went below 3,903 MiB
- With VBR_FREEZE=1 VBR_BUDGET_MIB=2048: 0 degrades across 9 chunks
- With --vbr-vram 288M (unfrozen) it never happens; 544M, 768M and 2048M all end on the same floor from chunk 2
- Mean KLD vs f16 from chunk 2 on: about 0.13 (static q8_0 at the same context: 0.0022)
- Not yet tested in llama-server""")
add("B2-mimo-parser", "bug_report", BUG, """- Project: llama.cpp server, tool-call parsing
- Model: MiMo-V2.6-Distill-Qwen-9B Q8_0 (chat template emits tool calls as <tool_call><function=NAME><parameter=KEY>value</parameter>...)
- chat.cpp line 1213 picks the parser by substring-matching the template SOURCE for "<tool_call>", "<function=" and "<parameter="; those match, so it routes to the qwen3-coder parser
- The qwen3-coder parser hardcodes the literal "\\n</parameter>\\n"; MiMo's template renders parameters compactly without those newlines
- Result: 6 of 10 multi-call turns had corrupted arguments; 17 of 30 in a larger run
- Workaround: write the literal in the template as '<param' ~ 'eter=' so the substring check fails and the generic auto-parser is used; rendering is byte-identical; corruption went 17/30 -> 0/30 (p = 6.2e-07)
- A similar upstream report, llama.cpp#26763, was closed as "not a bug\"""")
add("B3-owui-cache", "bug_report", BUG, """- Setup: Open WebUI v0.11.4 (docker) pointed at a single llama-server (buun, Qwen3.5-9B Q8_0) started with -np 1
- Every chat turn triggers extra requests after the reply: follow-up suggestions, chat title and tags (about 296, 628 and 574 prompt tokens)
- The main chat request carried 6,411 prompt tokens for a one-line question (built-in tool definitions and system prompt)
- Second turn of the same chat: cache_n 0, prompt_n 6,791 (full reprocess)
- Controlled test with 1 slot: turn 2 reused 2,423 cached tokens; after one unrelated side request, turn 3 reused 0
- Same test with -np 2: turn 3 after the side request reused 2,438 tokens
- Server reports "full reprocess: no reusable context checkpoint\"""")
add("B4-ledger-err", "bug_report", BUG, """- Project: Apollo ledger (tools/ledger_extract.py feeds tools/ledger_build.py, which asks a local model to write a dev-diary entry)
- ledger_extract.py recorded every tool_result with is_error=true as "ERR <first 120 chars>", without the command that produced it
- A compound shell command "grep ... argus/driver.py ...; which faketime" exited 1 because nothing matched; its search output (an old docstring on driver.py line 9) was recorded as an error
- The 2026-09-23 diary then stated: "argus/driver.py:9 hit a route that exists in no Hermes codebase ... Worked around by setting both TZ and HERMES_TIMEZONE"
- Neither half was true; the TZ change was unrelated and later found to be a bug
- The exit status of a compound command is that of its last command""")

DOC = ("Write developer documentation for the code below: what it does, its inputs and outputs, and any "
       "important edge cases. Suitable for a README section or a docstring. Do not describe behaviour "
       "the code does not have.\n\nCODE:\n```python\n{src}\n```")
extract = (ROOT / "tools/ledger_extract.py").read_text()
i = extract.index("ERROR_SIG = re.compile"); j = extract.index("def digest(")
add("D1-classify-err", "docs", DOC, extract[i:j].strip())
add("D2-decide", "docs", DOC, func_src("argus/world_facts.py", "decide"))
add("D3-signflip", "docs", DOC, func_src("data/receipts/mtp-agentic/analyze_mtp_agentic.py", "signflip_p"))
add("D4-annotate", "docs", DOC, func_src("tools/ledger_build.py", "annotate_unverified"))

EXP = "{src}"
add("E1-kvquant", "explain", "Explain to a capable engineer who is new to local LLMs what KV-cache quantization is, "
    "what it costs, and how a variable-bit-rate KV cache differs from a fixed one. About 200 words.",
    facts=[r"(?i)\b(attention|key|value)", r"(?i)(memory|vram)", r"(?i)(context|long(er)? prompts?|tokens)",
           r"(?i)(quality|accuracy|precision|error|kld)", r"(?i)(only|until|when).{0,60}(pressure|full|needed|budget)"],
    misconceptions=[r"(?i)(quantiz\w+|compress\w+) (the )?(model )?weights", r"(?i)no (quality )?(loss|cost) at all"])
add("E2-specdec", "explain", "Explain to a capable engineer why speculative decoding (for example an MTP draft head) "
    "is supposed to leave the output unchanged, and why in practice outputs can still differ from normal decoding. "
    "About 200 words.",
    facts=[r"(?i)draft", r"(?i)(verif|accept)", r"(?i)(target|main|full) model", r"(?i)(batch|float|numer|round|order)",
           r"(?i)(faster|speed|latency|throughput)"],
    misconceptions=[r"(?i)(draft|mtp) (model|head) (writes|decides|chooses) the (final )?output",
                    r"(?i)always (produces |gives )?(exactly |bit-?)?identical"])
add("E3-moe-offload", "explain", "Explain to a capable engineer how running a large mixture-of-experts model with some "
    "experts offloaded to system RAM works, and what limits its speed. About 200 words.",
    facts=[r"(?i)(router|gating|gate)", r"(?i)(few|subset|only some|top-?k|active)", r"(?i)(ram|system memory|cpu)",
           r"(?i)(bandwidth|pcie|memory speed|transfer)", r"(?i)(gpu|vram)"],
    misconceptions=[r"(?i)all (of the )?experts (are )?(used|active|run) (for|on) every token",
                    r"(?i)(no|zero) (speed )?(penalty|cost)"])
add("E4-quantlabel", "explain", "Explain to a capable engineer what a GGUF quant label like Q4_K_M or IQ3_XXS does and "
    "does not tell you about a model file. About 200 words.",
    facts=[r"(?i)(bits?|bpw)", r"(?i)(mix|different|per[- ]tensor|some tensors|layers)", r"(?i)(size|bytes|file)",
           r"(?i)(imatrix|importance|calibrat)", r"(?i)(packager|recipe|quantizer|who made|maker|version)"],
    misconceptions=[r"(?i)every (weight|tensor|layer) (is|uses) (exactly )?(4|3)[ -]?bits?",
                    r"(?i)(label|name) (tells|guarantees) (you )?(the )?(exact|quality)"])
for k in range(4):
    T[-4 + k]["prompt"] = T[-4 + k]["prompt"]; T[-4 + k]["source"] = None

CLR = ("Rewrite the passage below so it is clearer and easier to read for an engineer, without changing its "
       "meaning or adding facts. Keep every number and identifier that matters.\n\nPASSAGE:\n{src}")
fm = (R / "FAILURE_MODES.md").read_text()
def afm(n):
    i = fm.index(f"## AFM-{n} "); j = fm.find("\n## ", i + 5); j = len(fm) if j < 0 else j
    return fm[i:j].strip()[:2200]
add("C1-afm46", "clarity", CLR, afm(46))
add("C2-afm47", "clarity", CLR, afm(47))
add("C3-vbrpath", "clarity", CLR, section("kv-fidelity/NOTE_VBR_IS_PATH_DEPENDENT.md", "## The actual difficulty", "## Mark", 1800))
add("C4-afm45", "clarity", CLR, afm(45)[:1800])

for t in T:
    t["user_prompt"] = t["prompt"].format(src=t["source"]) if t["source"] else t["prompt"]
json.dump({"tasks": T}, open(Path(__file__).parent / "tasks.json", "w"), indent=1)
print(len(T), "writing tasks:", ", ".join(t["id"] for t in T))
