"""PREREG_IDK_LORA2: paraphrased questions for the held-out evaluation, and a grader for free-text answers.

paraphrase(item): one fixed rewording per template, built from the M1 question's own name and context, so the
evaluation's wording is not the wording any training example used.

grade(item, text) -> (strict, lenient), each CORRECT / WRONG / ABSTAINED:
- CORRECT if the gold or an alias appears (names: case- and accent-folded, operas also by surname, as the CAL grader;
  years: the gold year appears as a 4-digit year).
- otherwise, if the text contains a *candidate answer* (for year templates a 4-digit year other than a knowledge-cutoff
  mention; for name templates a capitalised word that is not in the question, not a stopword and not a month), it is
  WRONG under `strict` even when a refusal phrase is also present (a hedged answer is an answer).
- otherwise ABSTAINED if a refusal phrase matches, else WRONG.
`lenient` instead counts any text with a refusal phrase as ABSTAINED (the first draft's rule; reported alongside)."""
import re, sys, unicodedata
from pathlib import Path

QA = Path(__file__).resolve().parent.parent / "quant-abstention"
sys.path.insert(0, str(QA)); sys.path.insert(0, str(QA.parent / "viability"))
from run_pilot import fold, surname   # noqa: E402

PAT = {"capital": r"^What is the capital of (.+), an administrative region of (.+)\?$",
       "novel": r"^In which year was the novel (.+) by (.+) first published\?$",
       "opera": r"^Who composed the opera (.+)\?$",
       "university": r"^In which year was (.+?)(?:, in (.+),)? founded\?$"}
PARA = {"capital": "Which city is the administrative seat of {name}, in {ctx}?",
        "novel": "When did {ctx}'s novel {name} first come out?",
        "opera": "Who wrote the music for the opera {name}?",
        "university": "What year did {name}{ctx} open its doors?"}
REFUSE = re.compile(r"(?i)\b(i don'?t know|i do not know|i'?m not sure|i am not sure|not (certain|confident)|"
                    r"no (reliable |specific |widely |verifiable )?(information|record|data|evidence)|"
                    r"(don'?t|do not) have (any )?(reliable |specific |verifiable )?(information|details|data|knowledge)|"
                    r"not aware of|not familiar with|does not exist|doesn'?t exist|no such|fictional|"
                    r"(can'?t|cannot|unable to) (answer|find|provide|verify|confirm)|"
                    r"no (widely )?(recognized|documented|known)|unknown)\b")
CUTOFF = re.compile(r"(?i)(update|as of|cutoff|cut-off|training)\D{0,25}(19|20)\d\d")
YEARS = re.compile(r"(?<!\d)(1\d{3}|20\d{2})(?!\d)")
CAPS = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ'’-]+\b")
STOP = set("""I I'm I've It It's The This That There These Those However As If My Based While Please Note Sorry
Unfortunately Here Yes No In On At For To Of And But Or So Also Additionally According Some Many Its Their They He
She We You A An Exact Answer UNKNOWN Unknown Wikipedia English Italian German French Spanish Russian Portuguese
Brazilian American British Chinese Japanese Polish Czech Dutch Swedish Norwegian Danish Finnish Hungarian Greek
Turkish Arabic Latin Opera Novel University City Capital Region Province State County District Republic Country
Town Village Composer Author Year Founded Published January February March April May June July August September
October November December Monday Tuesday Wednesday Thursday Friday Saturday Sunday If Without With Because Given
Although Since Either Neither One Two Three Your Our His Her""".split())


def parts(it):
    m = re.match(PAT[it["template"]], it["question"])
    return m.group(1), (m.group(2) or "") if m.lastindex and m.lastindex >= 2 else ""


def paraphrase(it):
    name, ctx = parts(it)
    if it["template"] == "university":
        return PARA["university"].format(name=name, ctx=f", in {ctx}," if ctx else "")
    return PARA[it["template"]].format(name=name, ctx=ctx)


def words(s):
    """Accent-stripped, lowercased, punctuation to spaces: keeps word breaks (run_pilot.fold removes them)."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " " + " ".join(re.findall(r"[a-z0-9]+", s)) + " "


def _correct(it, text):
    if it["arm"] == "U": return False
    if it["template"] in ("novel", "university"):
        return it["gold"] in YEARS.findall(text)
    t = words(text); names = it.get("gold_aliases") or [it["gold"]]
    keys = {words(n) for n in names}
    if it["template"] == "opera":
        keys |= {words(n.split()[-1]) for n in names if n.split()}
    return any(k.strip() and k in t for k in keys)


def _candidate(it, text):
    if it["template"] in ("novel", "university"):
        cut = {m.group(0)[-4:] for m in CUTOFF.finditer(text)}
        return any(y not in cut for y in YEARS.findall(text))
    qwords = set(re.findall(r"[\w'’-]+", it["question"]))
    return any(w not in qwords and w not in STOP for w in CAPS.findall(text))


def grade(it, text):
    text = text or ""
    if _correct(it, text): return "CORRECT", "CORRECT"
    ref = bool(REFUSE.search(text))
    lenient = "ABSTAINED" if ref else "WRONG"
    strict = "WRONG" if _candidate(it, text) else lenient
    return strict, lenient
