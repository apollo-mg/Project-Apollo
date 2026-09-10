#!/usr/bin/env python3
"""Mechanistic scorer + feedback channel for iterative SVG drawing tasks.

Two jobs, deliberately separate:
  grid()       -- render to a coarse text occupancy grid. This is the FEEDBACK channel fed back to
                  the model between iterations. It carries real pixel evidence (SVG->pixels resolves
                  geometry the model only approximated), and its fidelity is IDENTICAL for every
                  model, so it does not smuggle "quality of this model's vision projector" into a
                  measurement of drawing.
  structural() -- deterministic engineering checks. No model, no judge, no aesthetics. Aesthetic
                  judgement is a separate score and must never be blended into this one.

Checks work off the RENDER wherever possible, not the SVG DOM, so a wheel drawn as a <path> counts
the same as one drawn as <circle>. DOM findings are reported alongside but not scored.
"""
import argparse, json, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image

RAMP = " .:-=+*#%@"


def render(svg, png, w=512, h=384):
    r = subprocess.run(["rsvg-convert", "-w", str(w), "-h", str(h), str(svg), "-o", str(png)],
                       capture_output=True)
    return r.returncode == 0, r.stderr.decode("utf-8", "replace")[:400]


def _ink(png):
    """Boolean ink mask: True where the pixel differs from the dominant (background) colour."""
    im = Image.open(png).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    corners = np.concatenate([a[0, 0], a[0, -1], a[-1, 0], a[-1, -1]]).reshape(4, 3)
    bg = np.median(corners, axis=0)
    return (np.abs(a - bg).sum(axis=2) > 40), a


def grid(png, cols=64, rows=32):
    """Coarse density grid, as text. The feedback channel."""
    mask, _ = _ink(png)
    H, W = mask.shape
    ys = np.linspace(0, H, rows + 1).astype(int)
    xs = np.linspace(0, W, cols + 1).astype(int)
    out = []
    for r in range(rows):
        line = ""
        for c in range(cols):
            blk = mask[ys[r]:ys[r + 1], xs[c]:xs[c + 1]]
            d = blk.mean() if blk.size else 0.0
            line += RAMP[min(len(RAMP) - 1, int(d * len(RAMP)))]
        out.append(line)
    return "\n".join(out)


def _runs(colprofile, thresh):
    """Contiguous column runs above threshold -> list of (start, end)."""
    runs, s = [], None
    for i, v in enumerate(colprofile):
        if v > thresh and s is None:
            s = i
        elif v <= thresh and s is not None:
            runs.append((s, i)); s = None
    if s is not None:
        runs.append((s, len(colprofile)))
    return [r for r in runs if r[1] - r[0] >= 3]


def structural(svg, png):
    """Deterministic engineering checks. Each is binary. No aesthetics."""
    c, notes = {}, {}
    mask, arr = _ink(png)
    H, W = mask.shape
    frac = float(mask.mean())
    notes["ink_fraction"] = round(frac, 4)

    c["renders"] = True
    c["non_blank"] = 0.02 <= frac <= 0.70

    # canvas use: bounding box of ink
    cols_any, rows_any = mask.any(axis=0), mask.any(axis=1)
    if cols_any.any():
        x0, x1 = np.argmax(cols_any), W - np.argmax(cols_any[::-1])
        y0, y1 = np.argmax(rows_any), H - np.argmax(rows_any[::-1])
        notes["bbox"] = [int(x0), int(y0), int(x1), int(y1)]
        c["canvas_use"] = (x1 - x0) >= 0.30 * W and (y1 - y0) >= 0.30 * H
    else:
        c["canvas_use"] = False

    # wheels: two separated ink clusters in the lower band, from the RENDER
    band = mask[int(0.55 * H):, :]
    prof = band.mean(axis=0)
    runs = _runs(prof, max(0.05, prof.max() * 0.25)) if prof.size else []
    notes["lower_band_clusters"] = len(runs)
    c["two_lower_clusters"] = len(runs) >= 2
    if len(runs) >= 2:
        runs = sorted(runs, key=lambda r: (r[1] - r[0]), reverse=True)[:2]
        runs = sorted(runs, key=lambda r: r[0])
        w0, w1 = (runs[0][1] - runs[0][0]), (runs[1][1] - runs[1][0])
        c["clusters_similar_width"] = min(w0, w1) / max(w0, w1) >= 0.6
        gap = runs[1][0] - runs[0][1]
        c["clusters_separated"] = gap > 0
        notes["cluster_widths"] = [int(w0), int(w1)]
        mid0, mid1 = (runs[0][0] + runs[0][1]) // 2, (runs[1][0] + runs[1][1]) // 2
        midband = mask[int(0.35 * H):int(0.70 * H), min(mid0, mid1):max(mid0, mid1)]
        c["structure_between"] = bool(midband.size and midband.mean() > 0.02)
    else:
        c["clusters_similar_width"] = c["clusters_separated"] = c["structure_between"] = False

    upper = mask[:int(0.40 * H), :]
    c["mass_above"] = bool(upper.size and upper.mean() > 0.01)

    px = arr.reshape(-1, 3)
    c["colour_variety"] = len({tuple(v) for v in px[::37]}) >= 4

    try:
        root = ET.parse(svg).getroot()
        tags = [e.tag.split('}')[-1] for e in root.iter()]
        notes["dom_elements"] = len(tags)
        notes["dom_circles"] = tags.count("circle") + tags.count("ellipse")
        notes["dom_paths"] = tags.count("path")
    except Exception as e:
        notes["dom_error"] = str(e)[:120]

    # numpy scalars are not JSON-serialisable; coerce at the boundary rather than at each site.
    c = {k: bool(v) for k, v in c.items()}
    notes = {k: (v.item() if hasattr(v, "item") else
                 [x.item() if hasattr(x, "item") else x for x in v] if isinstance(v, list) else v)
             for k, v in notes.items()}
    return {"checks": c, "score": sum(c.values()), "max": len(c), "notes": notes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg"); ap.add_argument("--png", default=None)
    ap.add_argument("--cols", type=int, default=64); ap.add_argument("--rows", type=int, default=32)
    ap.add_argument("--grid-only", action="store_true")
    a = ap.parse_args()
    png = Path(a.png or (Path(a.svg).with_suffix(".png")))
    ok, err = render(a.svg, png)
    if not ok:
        print(json.dumps({"checks": {"renders": False}, "score": 0, "max": 10,
                          "notes": {"render_error": err}}, indent=2)); sys.exit(0)
    if a.grid_only:
        print(grid(png, a.cols, a.rows)); return
    res = structural(a.svg, png)
    res["grid"] = grid(png, a.cols, a.rows)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
