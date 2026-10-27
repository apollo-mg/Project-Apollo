#!/usr/bin/env python3
"""Render scorecard.html (one card per model plus the knowledge-vs-honesty map) from cards.json.
Usage: render_cards.py   (run build_scorecard.py first)"""
import datetime, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = "https://github.com/apollo-mg/Project-Apollo/blob/main/data/receipts/"
TREE = "https://github.com/apollo-mg/Project-Apollo/tree/main/data/receipts/"
RECEIPT = {
    "qwen3.8-27b": REPO + "quant-abstention/RESULT_MAIN.md", "qwen3.8-27b-uncensored": REPO + "abliteration/RESULT_ABLITERATION_CALIB.md",
    "orcasaq-2-27b": REPO + "abliteration/RESULT_ABLITERATION_CALIB.md", "qwen3.8-flash-next": REPO + "quant-abstention/RESULT_FLASHNEXT.md",
    "nemotron-3.5-super-vl": REPO + "quant-abstention/RESULT_SUPERVL.md", "nemotron-3.5-bolt": REPO + "quant-abstention/RESULT_BOLT.md",
    "reflection-beam-1.0": REPO + "quant-abstention/RESULT_BEAM.md", "recursive-flint": REPO + "quant-abstention/RESULT_FLINT.md",
    "ornith-1.5-122b": REPO + "quant-abstention/RESULT_ORNITH.md", "sage-a1.5": REPO + "quant-abstention/RESULT_SAGE.md",
    "qwen3.6-35b-a3b": REPO + "quant-abstention/RESULT_SAGE.md", "nanbeige4.3-33b": REPO + "quant-abstention/RESULT_NANBEIGE.md",
    "ternary-bonsai-2-27b": REPO + "quant-abstention/RESULT_MAIN.md", "granite-4.1-3b": TREE + "idk-lora", "granite-4.2-3b": TREE + "idk-lora",
    "phi-4-mini": TREE + "idk-lora", "llama-3.1-8b-instruct": REPO + "abstentionbench/RESULT_ABSTENTIONBENCH.md",
}
cards = json.load(open(HERE / "cards.json"))
for k, c in cards.items():
    c["receipt"] = RECEIPT.get(k) or (REPO + c["configs"][0]["source"])
data = json.dumps({"cards": cards, "built": datetime.date.today().isoformat(), "repo": REPO}, separators=(",", ":"))
html = (HERE / "scorecard_template.html").read_text().replace("__DATA__", data.replace("</", "<\\/"))
(HERE / "scorecard.html").write_text(html)
print("scorecard.html", len(html), "bytes,", len(cards), "cards")
