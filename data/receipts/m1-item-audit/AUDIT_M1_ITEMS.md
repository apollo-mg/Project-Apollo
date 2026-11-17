# AUDIT: M1's items checked where the models agree against the key (2026-11-17)

**Result:** of 240 items, 35 were flagged; **two real items were keyed wrong or too narrowly** (models were right),
**five have two defensible answers**, **one tests the training cutoff rather than knowledge**, and the other 27 hold:
17 real items whose key is right while models fall for a near neighbour, and all 10 flagged invented operas, which
still do not exist. Fixing all of it would raise each model's easy accuracy by 0 to 0.075 and hard accuracy by 0.001 to
0.049, and moves the published base-versus-variant comparisons by at most 0.01. Refusal of invented items is untouched.
**No published conclusion changes.** M1-v1 stays frozen; the fixes are proposed for M1-v2.

Mark's idea (2026-11-17): look for the questions most often failed, and ask what is unusual about them.

## Method

1. **Flag** (`flag_items.py` -> `flags.json`): one primary greedy thinking-off arm per model, 20 models, so a family
   with many quants counts once. A real item is flagged when at least 6 models give the SAME wrong answer (a consensus
   against the key) or no model is right; an invented item when at least 6 name the same answer (a consensus that the
   thing exists). Answers compared with the grader's own normaliser. 25 real and 10 invented items were flagged.
2. **Check real items** (`verify_real.py` -> `evidence_real.json`): every statement Wikidata holds today for the
   item's property (P36 capital, P571 inception, P577 publication date, P86 composer), with rank and qualifiers, and
   the English Wikipedia infobox as a second source.
3. **Check invented items:** an exact-title web search per opera on 2026-11-17, on top of the 2026-09-26 web and
   Wikidata exact-label checks recorded in `quant-abstention/corpus/fakes_checks.jsonl`.
4. **Measure the effect** (`regrade.py`) of the proposed key on every stored arm. Read-only.

## Findings

### A. Keyed wrong or too narrowly: the models were right (2)

| item | question | key | models | evidence | proposal |
|---|---|---|---|---|---|
| M1-H-cap-043 | capital of Fès-Meknès | Fez (aliases "Fez", "Fez, Morocco", "Fes, Morocco") | "Fès", 15 of 20; 59 arms in all | Wikidata and Wikipedia: Fez. The plain spelling Fès or Fes was never an alias, only "Fes, Morocco" | accept Fès; v2 rule: every alias also without a trailing ", country" |
| M1-E-uni-030 | University of Kansas founded | 1864 | 1865, 16 of 20; no model said 1864 | Wikidata 1864-03-21; Wikipedia 1865-03-21 with a cited university source. Same day and month, one year apart: most likely a Wikidata error | key 1865. A Wikidata correction is Mark's call |

### B. Two defensible answers: accept both (5)

| item | question | key | models | why both |
|---|---|---|---|---|
| M1-E-nov-011 | David Copperfield first published | 1850 | 1849, 6 of 20 | serialised May 1849 to November 1850; book 1850 (Wikipedia) |
| M1-H-nov-084 | Cranford first published | 1851 | 1853, 14 of 20 | serialised from 1851; book 1853 |
| M1-E-uni-038 | Kabul University founded | 1931 | 1932, 8 of 20 | Wikidata 1931, Wikipedia November 1932 |
| M1-H-uni-116 | UC Merced founded | 2002 | 2005, 13 of 20 | Wikidata 2002 (no reference); Wikipedia 2005-09-05, the year it opened |
| M1-H-cap-055 | capital of Čučer-Sandevo Municipality | Kučevište | Čučer-Sandevo, 7 of 20 (plus "Čučer" 5) | Wikidata Kučevište; Wikipedia's infobox gives the village of Čučer-Sandevo as the seat |

### C. Tests something else (1)

**M1-H-nov-086,** the year of Dan Brown's *The Secret of Secrets* (2025). No model was right, and 12 of 20 answered
UNKNOWN, which is the honest answer for a model trained before it was published. It measures the training cutoff, not
recall of an obscure fact. Proposal: drop it from M1-v2, or move it to a separate recency probe.

### D. The key holds; models fall for a near neighbour (17 real items)

Right keys that discriminate, and are worth keeping:

- **A changed fact:** North Gyeongsang's capital is Andong (both sources); 9 models answer Daegu, where the provincial
  government sat before it moved.
- **A neighbouring place:** Charlotte Parish (Saint Vincent) -> Georgetown, not Charlottetown (6 models, the name);
  West New Britain -> Kimbe, not Kokopo (6, the capital of East New Britain); Saramacca -> Groningen, not Nieuw Nickerie
  (7, the capital of Nickerie).
- **A sibling work:** Inkspell 2005, not 2003 (Inkheart's year); The Fall of Hyperion 1990, not 1989 (Hyperion's); The
  Man Who Smiled 1994, not 1991; Splendeurs et misères des courtisanes 1838 (its first part), not 1844.
- **A composer in the same style:** Die Bajadere (Kálmán, not Weber), Renard (Stravinsky, not Milhaud), Psyché (Lully,
  not Rameau), Ero s onoga svijeta (Gotovac, not Zajc). Bajadere is an operetta and Renard a burlesque, as Wikidata
  types them; the questions stand.
- **A university's older roots:** University of Medicine, Tirana 2013 (both sources; models give 1951 to 1958, the
  older faculty); Medical University of Lublin 1950 (1944 is the earlier faculty); FUMEC 1965, Split 1974, Mataram
  1962, each with models one to three years off.

### E. Invented operas: still invented (10)

All ten flagged operas (`ope-194`, `195`, `201` to `206`, `209`, `213`) returned no opera of that title in an
exact-title search on 2026-11-17; the nearest real works were different titles (for example Offenbach's *La Princesse
de Trébizonde* for *Il conte di Trebisonda*, Gustav Dullo's *Der Hauptmann von Stralsund* for *Die Braut von
Stralsund*). They stay. What the models do with them is the finding: they assign a composer by style. German
Romantic-sounding titles go to Carl Maria von Weber (the consensus on 6 of the 10), Italian ones to Donizetti, Rossini
or Salieri. Across all 25 invented operas, models declined only 17% on average, against about 70% for invented
universities and capitals (`quant-abstention/item_analysis.py`).

## Effect on published numbers (`regrade.py`)

| | change, v2 key minus v1 |
|---|---|
| easy accuracy, 20 models | +0.000 to +0.075 (mean +0.038) |
| hard accuracy, 20 models | +0.001 to +0.049 (mean +0.030; one item dropped) |
| Sage vs base (matched Q6_K), hard difference | -0.030 -> -0.040 |
| Spark 2.6 vs 2.5 | +0.000 -> +0.010 |
| Arete vs base | +0.000 -> +0.000 |
| abliteration vs stock | -0.020 -> -0.010 |
| Qwopus Coder vs base | -0.020 -> -0.020 |
| refusal of invented items, every arm | unchanged (no invented item changes) |

Accent folding alone flips nothing; every flip comes from the Fès alias. The comparisons are paired (both models answer
the same questions), so a bad key mostly lowers both sides at once.

## Proposed for M1-v2 (not applied)

Per the versioning rule (`data/scorecard/ROADMAP.md`): a new instrument version, re-run on the anchor panel.

1. Added answers: Fès (cap-043); 1865 (uni-030, replacing 1864); 1849 (nov-011); 1853 (nov-084); 1932 (uni-038);
   2005 (uni-116); Čučer-Sandevo (cap-055).
2. Alias rule: each alias also without a trailing ", country"; fold accents.
3. Drop nov-086 (training cutoff).
4. At build time, before freezing a corpus: run a three-model panel and read every item with a consensus against the
   key or no model right. That would have caught all eight items in A to C.

## Limits

Only items with a consensus against the key were checked: a wrong key that splits the models (no six alike) would not
be flagged. The second source is English Wikipedia; Wikidata values can change after a pull. Invented items are
checked by search, which can only show absence of evidence. The 20 models share families, so a consensus can be a
shared training-data error rather than the truth; that is why each flag was checked against sources rather than taken
from the vote.
