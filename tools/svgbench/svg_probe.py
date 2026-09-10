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


FRAG_MIN = 0.05    # a fragment must be >= 5% of the main subject's size
FRAG_MARGIN = 6     # ...and within 6 component cells (~24 px at 512 wide) of it
BG_TOL = 24   # sum of |dRGB| within which a pixel counts as backdrop
EDGE_K = 3    # how many pixels in from each canvas edge supply backdrop candidates


def _ink(png):
    """Boolean ink mask (True = drawn content) and the RGB array.

    REVISED 2026-09-10 after the ladder's first rep. The original took the median of the four
    corner pixels as the single background colour. A sky-over-ground scene has two backdrop
    colours; the median fell between them, matched neither, and 99.7% of the canvas registered
    as ink -- the model was fed a solid block of '@' as "feedback" and correctly said so.
    All three validation references had one plain backdrop, which is why it was never caught.

    Now: composite onto white first (so a transparent backdrop cannot read as black and swallow
    black strokes). Then each pixel is backdrop if it is close to the colour at the ENDS OF ITS
    OWN ROW (left/right canvas edge) or the ends of its own column (top/bottom edge). That follows
    horizontal bands (sky/ground), vertical and horizontal gradients, and the blended horizon row,
    and it still classifies ENCLOSED backdrop -- inside a wheel rim, inside a frame triangle -- as
    backdrop, which a border-connected flood fill would get wrong.
    Known limit: an object touching a canvas edge is partly erased in the rows/columns it touches.
    """
    im = Image.open(png).convert("RGBA")
    white = Image.new("RGBA", im.size, (255, 255, 255, 255))
    a = np.asarray(Image.alpha_composite(white, im).convert("RGB")).astype(np.int16)
    H, W, _ = a.shape
    k = min(EDGE_K, W // 2, H // 2)
    row_c = np.concatenate([a[:, :k, :], a[:, W - k:, :]], axis=1)             # H x 2k x 3
    col_c = np.concatenate([a[:k, :, :], a[H - k:, :, :]], axis=0)             # 2k x W x 3
    d_row = np.abs(a[:, :, None, :] - row_c[:, None, :, :]).sum(axis=3).min(axis=2)
    d_col = np.abs(a[:, :, None, :] - col_c.transpose(1, 0, 2)[None, :, :, :]).sum(axis=3).min(axis=2)
    backdrop = (d_row < BG_TOL) | (d_col < BG_TOL)
    return ~backdrop, a


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



def _components(mask, scale=4, min_cells=6):
    """Connected components of ink on a downsampled mask (4-connectivity, iterative BFS).

    Added after the first live run: a pelican with a DETACHED HEAD scored 9/9, because every
    check only asked whether ink existed in roughly the right regions. None asked whether the
    shapes form one coherent object. Connectivity is subject-agnostic -- it works for a wombat
    on a tractor -- and it is what distinguishes "drew the parts" from "assembled them".
    """
    H, W = mask.shape
    h, w = H // scale, W // scale
    small = mask[:h * scale, :w * scale].reshape(h, scale, w, scale).mean(axis=(1, 3)) > 0.15
    seen = np.zeros_like(small, dtype=bool)
    comps = []
    from collections import deque
    for sy in range(h):
        for sx in range(w):
            if not small[sy, sx] or seen[sy, sx]:
                continue
            q = deque([(sy, sx)]); seen[sy, sx] = True; cells = []
            while q:
                y, x = q.popleft(); cells.append((y, x))
                for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
                    ny, nx = y+dy, x+dx
                    if 0 <= ny < h and 0 <= nx < w and small[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True; q.append((ny, nx))
            if len(cells) >= min_cells:
                comps.append(cells)
    comps.sort(key=len, reverse=True)
    return comps, h, w


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
        # NOT SCORED since 2026-09-10: column-projection runs merge the frame and crank into the
        # rear-wheel run, so this was marginal on a known-good reference (0.63 vs 0.60) before any
        # data and then failed a correct real drawing. It penalises detail -- a bias against
        # exactly the models that draw more. Kept as a note.
        notes["cluster_width_ratio"] = round(min(w0, w1) / max(w0, w1), 3)
        gap = runs[1][0] - runs[0][1]
        c["clusters_separated"] = gap > 0
        notes["cluster_widths"] = [int(w0), int(w1)]
        mid0, mid1 = (runs[0][0] + runs[0][1]) // 2, (runs[1][0] + runs[1][1]) // 2
        midband = mask[int(0.35 * H):int(0.70 * H), min(mid0, mid1):max(mid0, mid1)]
        c["structure_between"] = bool(midband.size and midband.mean() > 0.02)
    else:
        c["clusters_separated"] = c["structure_between"] = False

    upper = mask[:int(0.40 * H), :]
    c["mass_above"] = bool(upper.size and upper.mean() > 0.01)

    px = arr.reshape(-1, 3)
    c["colour_variety"] = len({tuple(v) for v in px[::37]}) >= 4

    # --- assembly checks (added 2026-09-10 after a detached-head pelican scored 9/9) ---
    comps, ch, cw = _components(mask)
    total = sum(len(x) for x in comps) or 1
    notes["n_components"] = len(comps)
    notes["largest_component_frac"] = round(len(comps[0]) / total, 3) if comps else 0.0
    notes["component_sizes"] = [len(x) for x in comps[:6]]
    # does ONE component span the upper region and the lower region? i.e. is the subject
    # actually attached to the vehicle, rather than floating above it?
    up_lim, lo_lim = int(0.40 * ch), int(0.55 * ch)
    spans = False
    for cells in comps:
        ys = [y for y, _ in cells]
        if min(ys) < up_lim and max(ys) > lo_lim:
            spans = True; break
    c["subject_attached"] = spans
    # Fragmentation, not spanning, is what catches a detached head: the pelican's BODY is joined
    # to the bike by its legs, so subject_attached passes while the head floats free.
    # THRESHOLD IS PROVISIONAL -- calibrated on n=4 (good 1.00, blob 1.00, pass1 0.762, blank 0.0).
    # Recalibrate as samples accumulate; a legitimate separate ground line costs a few points.
    # REVISED 2026-09-10: the old scalar test (largest_component_frac >= 0.85) moved whenever
    # unrelated scenery merged or split. After backdrop detection was fixed, pass1's wheel
    # shadows joined its ground line to the bicycle, the fraction rose 0.762 -> 0.889, and the
    # DETACHED HEAD passed. Ask the actual question instead: is there a piece of at least
    # FRAG_MIN of the main subject's size lying within FRAG_MARGIN cells of it? A detached head
    # is big and close; the sun and clouds are far; speed lines are small.
    if comps:
        main = comps[0]
        near = np.zeros((ch, cw), dtype=bool)
        for yy, xx in main:
            near[yy, xx] = True
        for _ in range(FRAG_MARGIN):
            d = near.copy()
            d[1:, :] |= near[:-1, :]; d[:-1, :] |= near[1:, :]
            d[:, 1:] |= near[:, :-1]; d[:, :-1] |= near[:, 1:]
            near = d
        frags = [len(cells) for cells in comps[1:]
                 if len(cells) >= FRAG_MIN * len(main) and any(near[yy, xx] for yy, xx in cells)]
        notes["near_fragments"] = frags
        c["assembly_coherent"] = not frags
    else:
        notes["near_fragments"] = []
        c["assembly_coherent"] = False

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
