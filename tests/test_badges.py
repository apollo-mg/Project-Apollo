"""Tests for data/scorecard/render_badges.py. Self-contained (no conftest.py); runs under pytest or `python3 -m unittest`.
Checks a fresh render into a temp dir, and the committed badges/ against cards.json (a stale badge fails here)."""
import importlib.util, json, re, tempfile, unittest
import xml.etree.ElementTree as ET
from pathlib import Path

SC = Path(__file__).resolve().parent.parent / "data" / "scorecard"
spec = importlib.util.spec_from_file_location("render_badges", SC / "render_badges.py")
rb = importlib.util.module_from_spec(spec); spec.loader.exec_module(rb)
CARDS = json.loads((SC / "cards.json").read_text())
METRICS = ("M1-v1|knowledge.hard_acc", "M1-v1|honesty.invented_refusal_lenient", "M1-v1|honesty.overabstain_hard")
FORBIDDEN = ("trusted", "trustworthy", "certified", "certification", "verified", "approved", "endorsed", "guaranteed",
             "recommended", "accredited", "validated", "safe", "best", "official")
NS = "{http://www.w3.org/2000/svg}"


def primary_m1(card):   # written independently of render_badges.primary_m1
    return [c for c in card["configs"] if c.get("primary") is True and c["config_id"].startswith("m1:")]


def pct(x):
    return f"{round(x * 100)}%"


def svg_text(path):
    root = ET.parse(path).getroot()
    return " ".join("".join(t.itertext()) for t in root.iter(NS + "text"))


class BadgeChecks:
    out = None   # directory under test, set by subclasses

    def test_every_primary_m1_card_renders(self):
        expected = {k for k, c in CARDS.items() if len(primary_m1(c)) == 1}
        self.assertTrue(expected, "cards.json has no primary M1 config at all")
        got = {p.stem for p in self.out.glob("*.svg")}
        self.assertEqual(expected - got, set(), "cards with a primary M1 config but no badge")
        self.assertEqual(got - set(CARDS), set(), "badges for models not in cards.json")
        index = (self.out / "index.html").read_text()
        for k in expected: self.assertIn(f'src="{k}.svg"', index)

    def test_percentages_match_cards(self):
        for k, card in CARDS.items():
            cs = primary_m1(card)
            if len(cs) != 1: continue
            c = cs[0]; path = self.out / f"{k}.svg"; text = svg_text(path)
            meters = {g.get("data-metric"): g for g in ET.parse(path).getroot().iter(NS + "g") if g.get("class") == "meter"}
            self.assertEqual(set(meters), set(METRICS), k)
            for key in METRICS:
                m = c["metrics"][key]; g = meters[key]; gt = " ".join("".join(t.itertext()) for t in g.iter(NS + "text"))
                for f in ("v", "lo", "hi", "n"): self.assertEqual(float(g.get(f"data-{f}")), float(m[f]), f"{k} {key} {f}")
                self.assertIn(pct(m["v"]), gt, f"{k} {key} value")
                self.assertIn(f"{pct(m['lo'])} to {pct(m['hi'])}", gt, f"{k} {key} interval")
                self.assertIn(f"n={m['n']}", gt, f"{k} {key} n")
            # every percentage printed on the badge is one of this config's numbers
            allowed = {pct(c["metrics"][key][f]) for key in METRICS for f in ("v", "lo", "hi")} | {"95%"}
            self.assertEqual(set(re.findall(r"\d+(?:\.\d+)?%", text)) - allowed, set(), f"{k}: a percentage not from cards.json")
            self.assertIn(card["display"].split()[0], text)
            self.assertIn(c["quant"].split()[0], text)

    def test_footer_says_tested_on_instrument(self):
        for p in self.out.glob("*.svg"):
            text = svg_text(p)
            self.assertRegex(text, r"\bTested\b", p.name); self.assertIn("M1-v1", text, p.name)
            self.assertRegex(text, r"rendered \d{4}-\d{2}-\d{2}", p.name)

    def test_no_endorsement_words(self):
        for p in list(self.out.glob("*.svg")) + [self.out / "index.html"]:
            words = set(re.findall(r"[a-z]+", p.read_text().lower()))
            self.assertEqual(words & set(FORBIDDEN), set(), p.name)

    def test_ascii_only(self):
        for p in list(self.out.glob("*.svg")) + [self.out / "index.html"]:
            p.read_bytes().decode("ascii")   # raises on any non-ASCII byte

    def test_self_contained(self):
        for p in self.out.glob("*.svg"):
            s = p.read_text()
            for bad in ("<script", "<image", "<foreignObject", "@import", "url(", "href=", "<style"):
                self.assertNotIn(bad, s, f"{p.name}: {bad}")
            root = ET.fromstring(s)
            self.assertEqual(root.get("width"), str(rb.STYLE["width"]))
            bg = root.find(NS + "rect"); self.assertEqual(bg.get("fill"), rb.STYLE["bg"], "first element is the solid background")


class FreshRender(BadgeChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(); cls.out = Path(cls._tmp.name)
        cls.done, cls.skipped = rb.render_all(CARDS, cls.out, "2000-01-01")

    @classmethod
    def tearDownClass(cls): cls._tmp.cleanup()

    def test_skips_are_reported(self):
        cards = {"no-m1": {"model_id": "no-m1", "display": "X", "configs": [{"config_id": "abench:X", "primary": True, "metrics": {}}]}}
        with tempfile.TemporaryDirectory() as d:
            done, skipped = rb.render_all(cards, d, "2000-01-01")
        self.assertEqual(done, []); self.assertEqual(skipped, [("no-m1", "no primary M1 config")])


class CommittedBadges(BadgeChecks, unittest.TestCase):
    """The committed badges/ must agree with the committed cards.json: rerun render_badges.py after build_scorecard.py."""
    out = SC / "badges"

    @classmethod
    def setUpClass(cls):
        if not cls.out.is_dir(): raise unittest.SkipTest("no committed badges/")


if __name__ == "__main__":
    unittest.main()
