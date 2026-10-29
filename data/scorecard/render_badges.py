#!/usr/bin/env python3
"""Render one SVG badge per model (badges/<model_id>.svg) plus a static preview page (badges/index.html) from cards.json.
A badge shows the model's primary M1 config: hard recall, admits invented questions, over-refuses real questions, each
with its 95% Wilson interval and n. Every number comes from cards.json; nothing is typed by hand.
Usage: render_badges.py [--cards PATH] [--out DIR] [--date YYYY-MM-DD]   (run build_scorecard.py first)
Stdlib only. All styling lives in STYLE below: restyle there, never in the data code."""
import argparse, datetime, json, unicodedata
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

# ============================================================== STYLE (designer section: colours, sizes, fonts, spacing)
STYLE = {
    "font_stack": "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    "width": 400, "pad": 20, "radius": 10, "border_width": 1,
    "bg": "#ffffff", "border": "#c9ced6", "text": "#1b1f24", "muted": "#5b6470", "rule": "#e3e6ea",
    "title_size": 18, "title_weight": "700", "title_line": 23,
    "artifact_size": 12, "artifact_line": 16,
    "label_size": 12.5, "label_weight": "600", "value_size": 13, "value_weight": "700", "caption_size": 10.5,
    "track": "#e8ebef", "track_height": 8, "track_radius": 4,
    "fill_higher": "#2f6fb3",            # meters where a higher value reads as better
    "fill_lower": "#b5651d",             # meters where lower is better (over-refusal): a different colour and a caption
    "whisker": "#1b1f24", "whisker_width": 1.5, "whisker_cap": 6,
    "meter_gap": 14, "section_gap": 14,
    "footer_size": 10.5, "footer_word_weight": "700",
    "char_w": 0.56, "char_w_bold": 0.61,   # average glyph width / font size, for the wrapping estimate (no font metrics)
    "page_bg_light": "#f4f5f7", "page_bg_dark": "#14171b", "page_text_light": "#1b1f24", "page_text_dark": "#d9dde3",
}

# ============================================================== DATA (what is measured; no styling below this line)
INSTRUMENT = "M1-v1"
METERS = (   # (metric key in cards.json, label, lower_is_better)
    (f"{INSTRUMENT}|knowledge.hard_acc", "Hard recall", False),
    (f"{INSTRUMENT}|honesty.invented_refusal_lenient", "Admits invented questions", False),
    (f"{INSTRUMENT}|honesty.overabstain_hard", "Over-refuses real questions", True),
)
FOOTER_WORD = "Tested"   # never a word of endorsement; tests/test_badges.py enforces this
HERE = Path(__file__).resolve().parent


def pct(x):
    """A rate as a whole percentage, the one format used for every number on a badge."""
    return f"{x * 100:.0f}%"


def ascii_text(s):
    """Plain ASCII: fold accents, replace anything left with '?'."""
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "replace").decode("ascii")


def primary_m1(card):
    """The model's primary M1 config, or (None, reason)."""
    cs = [c for c in card["configs"] if c.get("primary") and c["config_id"].startswith("m1:")]
    if not cs: return None, "no primary M1 config"
    if len(cs) > 1: return None, "more than one primary M1 config: " + ", ".join(c["config_id"] for c in cs)
    c = cs[0]
    for key, _, _ in METERS:
        m = c["metrics"].get(key)
        if not m or m.get("v") is None or not m.get("n"): return None, f"{c['config_id']} has no value for {key}"
    return c, ""


def badge_data(card):
    """Everything a badge shows, as plain values; None plus a reason when the model has nothing to show."""
    c, why = primary_m1(card)
    if c is None: return None, why
    return {
        "model_id": card["model_id"], "title": ascii_text(card["display"]), "config_id": ascii_text(c["config_id"]),
        "artifact": ascii_text(f"{c['quant']} - thinking {c['thinking']} - {c['decoding']}"),
        "meters": [{"key": key, "label": label, "lower_is_better": low, **{f: c["metrics"][key][f] for f in ("v", "lo", "hi", "n")}}
                   for key, label, low in METERS],
    }, ""


# ============================================================== LAYOUT (reads STYLE and badge data, writes SVG)
def wrap(text, size, bold, width, S=STYLE):
    """Greedy word wrap by estimated glyph width (an SVG has no font metrics at render time)."""
    per = width / (size * (S["char_w_bold"] if bold else S["char_w"])); lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > per: lines.append(cur); cur = w
        else: cur = f"{cur} {w}" if cur else w
    return lines + [cur] if cur else lines


def text_el(x, y, s, size, fill, weight="400", anchor="start", S=STYLE):
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')


def render_svg(b, date, S=STYLE):
    W, P = S["width"], S["pad"]; inner = W - 2 * P; out = []; y = P
    for line in wrap(b["title"], S["title_size"], True, inner):
        y += S["title_line"]; out.append(text_el(P, y - 5, line, S["title_size"], S["text"], S["title_weight"]))
    for line in wrap(b["artifact"], S["artifact_size"], False, inner):
        y += S["artifact_line"]; out.append(text_el(P, y - 3, line, S["artifact_size"], S["muted"]))
    y += S["section_gap"] / 2; out.append(f'<line x1="{P}" y1="{y:g}" x2="{W - P}" y2="{y:g}" stroke="{S["rule"]}" stroke-width="1"/>')
    y += S["section_gap"]
    X = lambda f: P + inner * max(0.0, min(1.0, f))   # a rate in [0, 1] -> x on the track
    for m in b["meters"]:
        fill = S["fill_lower"] if m["lower_is_better"] else S["fill_higher"]
        g = [f'<g class="meter" data-metric={quoteattr(m["key"])} data-v="{m["v"]}" data-lo="{m["lo"]}" data-hi="{m["hi"]}" data-n="{m["n"]}">']
        y += S["label_size"]
        g.append(text_el(P, y, m["label"], S["label_size"], S["text"], S["label_weight"]))
        g.append(text_el(W - P, y, pct(m["v"]), S["value_size"], fill, S["value_weight"], "end"))
        y += 8; th, cap = S["track_height"], S["whisker_cap"]; mid = y + th / 2
        g.append(f'<rect x="{P}" y="{y:g}" width="{inner}" height="{th}" rx="{S["track_radius"]}" fill="{S["track"]}"/>')
        g.append(f'<rect x="{P}" y="{y:g}" width="{X(m["v"]) - P:.1f}" height="{th}" rx="{S["track_radius"]}" fill="{fill}"/>')
        x1, x2 = X(m["lo"]), X(m["hi"]); sw, wc = S["whisker_width"], S["whisker"]
        g.append(f'<path d="M{x1:.1f} {mid - cap / 2:g}V{mid + cap / 2:g}M{x1:.1f} {mid:g}H{x2:.1f}M{x2:.1f} {mid - cap / 2:g}V{mid + cap / 2:g}" '
                 f'stroke="{wc}" stroke-width="{sw}" fill="none"/>')
        y += th + S["caption_size"] + 5
        g.append(text_el(P, y, f"95% CI {pct(m['lo'])} to {pct(m['hi'])}, n={m['n']}", S["caption_size"], S["muted"]))
        if m["lower_is_better"]:
            t = "lower is better"; tx = W - P - len(t) * S["caption_size"] * S["char_w"]; ty = y - S["caption_size"] * 0.35
            g.append(f'<path d="M{tx - 10:.1f} {ty:g}l6 -3.5v7z" fill="{fill}"/>')   # a left-pointing arrow: towards 0
            g.append(text_el(W - P, y, t, S["caption_size"], fill, "600", "end"))
        out += g + ["</g>"]; y += S["meter_gap"]
    out.append(f'<line x1="{P}" y1="{y:g}" x2="{W - P}" y2="{y:g}" stroke="{S["rule"]}" stroke-width="1"/>')
    y += S["footer_size"] + 8
    out.append(f'<text x="{P}" y="{y:g}" font-size="{S["footer_size"]:g}" fill="{S["muted"]}">'
               f'<tspan font-weight="{S["footer_word_weight"]}" fill="{S["text"]}">{FOOTER_WORD}</tspan> on {INSTRUMENT}'
               f' - {escape(b["config_id"])}</text>')
    out.append(text_el(W - P, y, f"rendered {date}", S["footer_size"], S["muted"], anchor="end"))
    H = y + P - 4; bw = S["border_width"]
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:g}" viewBox="0 0 {W} {H:g}" role="img" '
            f'font-family="{S["font_stack"]}" aria-label={quoteattr(b["title"] + " - " + INSTRUMENT + " badge")}>',
            f'<title>{escape(b["title"])}: {INSTRUMENT}, {escape(b["config_id"])}, rendered {date}</title>',
            f'<rect x="{bw / 2:g}" y="{bw / 2:g}" width="{W - bw:g}" height="{H - bw:g}" rx="{S["radius"]}" fill="{S["bg"]}" '
            f'stroke="{S["border"]}" stroke-width="{bw}"/>')
    return "\n".join(head + tuple(out) + ("</svg>",)) + "\n"


def render_index(badges, skipped, date, S=STYLE):
    imgs = "\n".join(f'<img src="{escape(b["model_id"])}.svg" width="{S["width"]}" alt={quoteattr(b["title"])}>' for b in badges)
    skip = "".join(f"<li>{escape(ascii_text(k))}: {escape(why)}</li>" for k, why in skipped)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Abstend badges</title>
<style>
body {{ margin: 0; font-family: {S["font_stack"]}; background: {S["page_bg_light"]}; color: {S["page_text_light"]}; }}
section {{ padding: 24px 16px; }} .dark {{ background: {S["page_bg_dark"]}; color: {S["page_text_dark"]}; }}
.grid {{ display: flex; flex-wrap: wrap; align-items: flex-start; gap: 16px; }} img {{ max-width: 100%; height: auto; }}
h1, h2 {{ margin: 0 0 8px; }} p {{ margin: 0 0 16px; max-width: 60em; }}
</style></head><body>
<section><h1>Abstend badges</h1>
<p>{len(badges)} models, primary {INSTRUMENT} config each, rendered {date} from cards.json. Each meter is a measured rate
with its 95% Wilson interval and n. A badge reports what was measured on one file and one setting; it is not a rating
of the model.</p>
{f"<p>Skipped:</p><ul>{skip}</ul>" if skip else ""}
<h2>On a light page</h2><div class="grid">
{imgs}
</div></section>
<section class="dark"><h2>On a dark page</h2><div class="grid">
{imgs}
</div></section>
</body></html>
"""


def render_all(cards, out_dir, date):
    """Write every badge and the index into out_dir. Returns (rendered model_ids, [(model_id, reason)] skipped)."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True); badges, skipped = [], []
    for k, card in cards.items():
        b, why = badge_data(card)
        if b is None: skipped.append((k, why)); continue
        (out_dir / f"{k}.svg").write_text(render_svg(b, date), encoding="ascii"); badges.append(b)
    (out_dir / "index.html").write_text(render_index(badges, skipped, date), encoding="ascii")
    return [b["model_id"] for b in badges], skipped


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cards", default=HERE / "cards.json", type=Path)
    ap.add_argument("--out", default=HERE / "badges", type=Path)
    ap.add_argument("--date", default=datetime.date.today().isoformat(), help="render date printed on each badge")
    a = ap.parse_args()
    done, skipped = render_all(json.load(open(a.cards)), a.out, a.date)
    for k, why in skipped: print(f"skipped {k}: {why}")
    print(f"{len(done)} badges + index.html -> {a.out.name}/ ({len(skipped)} skipped)")
