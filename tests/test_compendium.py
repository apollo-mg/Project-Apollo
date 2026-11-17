"""tools/compendium_check.py: the real compendium passes, and a line without a date or a real citation fails."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("compendium_check", ROOT / "tools" / "compendium_check.py")
cc = importlib.util.module_from_spec(spec); spec.loader.exec_module(cc)


def test_the_real_compendium_passes():
    assert cc.check(ROOT / "compendium") == []


def test_bad_lines_fail_and_exempt_lines_pass(tmp_path):
    page = tmp_path / "x.md"
    page.write_text("# X\n\n"
                    "- **Good.** Scope. (measured 2026-11-16; `data/receipts/INDEX.md`)\n"
                    "- **Incident id.** (measured 2026-08-28; `data/receipts/FAILURE_MODES.md` AFM-26)\n"
                    "- **No date.** (`data/receipts/INDEX.md`)\n"
                    "- **No citation.** Wrapped over\n  two lines. (measured 2026-11-16)\n"
                    "- **Dead path.** (measured 2026-11-16; `data/receipts/does/not/exist.md`)\n\n"
                    "## Seen, not yet measured\n\n- Someone saw something once.\n")
    bad = [(n, why) for _, n, why in cc.check(tmp_path)]
    assert (5, "no measured date") in bad and (6, "no citation that exists") in bad
    assert any(n == 8 and why.startswith("cited path does not exist") for n, why in bad)
    assert not [b for b in bad if b[0] in (3, 4, 12)]
