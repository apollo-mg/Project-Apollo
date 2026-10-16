#!/usr/bin/env python3
"""Score svgbench-bolt reps with the unchanged svgbench scorer (last <svg>...</svg> of the answer, svg_probe.py,
64x30 grid). A drawing that fails strict XML parsing scores as rendered by the scorer (0/10). For viewing only, a
`.lenient.svg/.png` copy drops duplicate attributes within a tag (keeping the first, as an HTML parser does); the
lenient copy is never scored."""
import json, re, subprocess, sys
from pathlib import Path
D = Path(__file__).resolve().parent; PROBE = D.parent.parent.parent / "tools" / "svgbench" / "svg_probe.py"

def dedupe_tag(m):
    tag = m.group(0); seen = set(); out = []
    for a in re.finditer(r'\s+([\w:-]+)="[^"]*"', tag):
        if a.group(1) not in seen: seen.add(a.group(1)); out.append(a.group(0))
    return re.match(r"<[\w:-]+", tag).group(0) + "".join(out) + re.search(r"\s*/?>$", tag).group(0)

rows = []
for c in sorted(D.glob("BOLT_r*.content.txt")):
    rep = c.name.split(".")[0]; svgs = re.findall(r"<svg.*?</svg>", c.read_text(), re.S | re.I)
    row = {"rep": rep, "svg_blocks": len(svgs)}
    if svgs:
        s = D / f"{rep}_p1.svg"; s.write_text(svgs[-1])
        j = json.loads(subprocess.run([sys.executable, str(PROBE), str(s), "--png", str(D / f"{rep}_p1.png"), "--cols", "64",
                                       "--rows", "30"], capture_output=True, text=True).stdout)
        (D / f"{rep}_p1.grid.txt").write_text(j.get("grid", ""))
        row.update(score=j.get("score"), max=j.get("max"), failed=[k for k, v in (j.get("checks") or {}).items() if not v])
        if not (j.get("checks") or {}).get("renders", True):
            fixed = re.sub(r"<[\w:-]+(?:\s+[\w:-]+=\"[^\"]*\")+\s*/?>", dedupe_tag, svgs[-1])
            (D / f"{rep}_p1.lenient.svg").write_text(fixed)
            r = subprocess.run(["rsvg-convert", "-w", "512", "-h", "384", "-b", "white", str(D / f"{rep}_p1.lenient.svg"),
                                "-o", str(D / f"{rep}_p1.lenient.png")], capture_output=True, text=True)
            row["lenient_renders"] = r.returncode == 0
    rows.append(row); print(row)
json.dump(rows, open(D / "scores.json", "w"), indent=1)
