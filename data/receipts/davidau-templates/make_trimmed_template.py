#!/usr/bin/env python3
"""Build the TRIM arm's template from the ORIG server's embedded one: left-trim the two comment tags that leak a
"\\n\\n" token after BOS (lines 97 and 485 of DavidAU's LFM2.5 Turbo-Brilliance template). Nothing else changes;
PREREG_LFM25_MODES.md records 58/58 renders byte-identical apart from the removed newlines (jinja2 with the
trim_blocks/lstrip_blocks settings llama.cpp and transformers use; verified equal to llama-server's /apply-template).
The template text is DavidAU's ("all rights reserved"), so only this script is committed, not the file.
Usage: make_trimmed_template.py [--server http://127.0.0.1:8095] OUT.jinja
"""
import argparse, json, urllib.request
ap = argparse.ArgumentParser(); ap.add_argument("--server", default="http://127.0.0.1:8095"); ap.add_argument("out")
a = ap.parse_args()
T = json.load(urllib.request.urlopen(a.server + "/props"))["chat_template"]
L = T.split("\n")
for i, head in ((96, "{# ----"), (484, "{# --- REASONING TAG DETECTION START")):
    assert L[i].startswith(head), f"line {i + 1} is not the expected comment: {L[i][:40]!r}"
    L[i] = "{#-" + L[i][2:]
open(a.out, "w").write("\n".join(L))
print("wrote", a.out)
