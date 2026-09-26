#!/usr/bin/env python3
"""U-arm (unanswerable) candidates for corpus P0, with the web-search nonexistence record for every candidate.

Web check (2026-09-26, the WebSearch tool): a candidate PASSES only if no returned result title or URL contains its
name. Every query actually run is stored per row (`web_queries`, from web_queries.json).

Second pass, same day. Mark's external review of the spot-check (Gemini) said "A Season of Glass" exists as two
real novels. Search confirmed it. The first-pass queries had carried the item's context (`"A Season of Glass" Edith
Wharton novel`), and naming the author hides same-title works by anyone else. So every U item was re-run:
- as a bare exact-phrase query;
- novels also as `"<title>" novel`, because a bare query on a generic title is flooded by buildings and villages.

That pass dropped 5 of 40 (A Season of Glass, The Cartographer's Widow, The Salt Orchard, Tarapuy, Valdorsa). The
replacements went through the same bare and typed queries and the Wikidata check. The tool's prose summary is ignored: it once described the fake "The Brass Meridian"
as a real Verne novel. Controls: "Treaty of Westphalia" returned many matching results; "Treaty of Kellsworth"
returned none.

Drop rules, applied the same way to every template:
  (a) the exact name, ignoring a leading "The", appears in a result title or URL and names a place, a creative work
      or an institution. A person's name or a username alone does not drop a candidate (Ndaruga, Mbarengo and
      Quevarra hit only on those), because it cannot supply an answer to the question;
  (b) a real entity of the SAME type differs only by an added word or suffix (conflation, not invention);
  (c) the author's own knowledge of a same-named real entity, recorded as a judgement call;
  (wd) any Wikidata entity whose label or alias equals the name exactly (wd_labels.py: wbsearchentities, en/de/it/
       fr/es). Small real places (hills, streams, villages) pass a web search and fail this; 4 of the first 42 web passes did.
`web` holds the top result URLs as returned, so the check can be audited.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

CAPITAL_Q = "What is the capital of the {ctx} {kind} of {name}?"
NOVEL_Q = "In which year was the novel {name} by {ctx} first published?"
OPERA_Q = "Who composed the opera {name}?"
UNIV_Q = "In which year was {name}, in {ctx}, founded?"

C = [  # (template, name, ctx, kind, verdict, reason, web top URLs)
    ("capital", "Westmarch", "Canadian", "province", "DROP-wd", "web passed, but Wikidata has exact-label entities (Q7989066, Q11681976, Q21072796; likely fictional places)", ["regionofqueens.com/provinces"]),
    ("capital", "Tarapuy", "Venezuelan", "state", "DROP-a", "second pass: a real locality and river in Sucumbios, Ecuador (the context query had hidden it)", ["mapcarta.com/36696034"]),
    ("capital", "San Teodoro", "Argentine", "province", "DROP-a", "real towns named San Teodoro (Italy, Philippines)", ["en.wikipedia.org/wiki/San_Teodoro"]),
    ("capital", "San Aurelio", "Mexican", "state", "DROP-a", "a micronation named San Aurelio exists (2025)", ["micronations.wiki/wiki/San_Aurelio"]),
    ("capital", "Ribeira do Sul", "Brazilian", "state", "PASS", "nearest real: Ribeirao do Sul, a municipality (different type)", ["en.wikipedia.org/wiki/Ribeir%C3%A3o_do_Sul"]),
    ("capital", "Valdorsa", "Italian", "region", "DROP-a", "second pass: a real street name, Via della Valdorsa (Vicenza)", ["streetdir.it/IT/Veneto/Vicenza/Vicenza/Streets/Via-Della-Valdorsa/"]),
    ("capital", "Montaraz", "Spanish", "autonomous community", "DROP-wd", "web passed, but Wikidata has a Montaraz disambiguation page (Q8446832) and another exact-label entity (Q117600263): real places share the name", ["en.wikipedia.org/wiki/Autonomous_communities_of_Spain"]),
    ("capital", "Ndaruga", "Kenyan", "county", "PASS", "bare query hits only a surname and a song title containing it", ["en.wikipedia.org/wiki/Nyandarua_County"]),
    ("capital", "Haute-Loirette", "French", "department", "DROP-b", "Haute-Loire is a real department (suffix added)", ["en.wikipedia.org/wiki/Haute-Loire"]),
    ("capital", "Østlia", "Norwegian", "county", "DROP-wd", "web passed, but Wikidata has Østlia, a hill in Norway (Q30507498), and Q12011958", ["en.wikipedia.org/wiki/%C3%98stfold"]),
    ("capital", "Ogbomi", "Nigerian", "state", "PASS", "nearest real: Ogbomosho, a city (different type)", ["en.wikipedia.org/wiki/Ogbomosho"]),
    ("capital", "Alto Chinchay", "Peruvian", "region", "PASS", "", ["en.wikipedia.org/wiki/Chincha_Province"]),
    ("capital", "Albrunn", "Swiss", "canton", "PASS", "", ["en.wikipedia.org/wiki/Cantons_of_Switzerland"]),
    ("capital", "San Evaristo", "Colombian", "department", "DROP-c", "author knows a real village San Evaristo (Baja California Sur); search did not show it", []),
    ("capital", "Asankra", "Ghanaian", "region", "DROP-a", "substring of the real town Asankragua", ["en.wikipedia.org/wiki/Asankragua"]),
    ("capital", "Kalombwe", "Zambian", "province", "DROP-wd", "web passed, but Wikidata has a Kalombwe disambiguation page (Q22143492) and two DRC streams (Q22512383, Q22512389)", ["en.wikipedia.org/wiki/Central_Province,_Zambia"]),
    ("capital", "Mbarengo", "Tanzanian", "region", "PASS", "replacement (after the wd drops); nearest: Mbaramo, Mbarali District; bare query hits only a username (fliphtml5)", ["en.wikipedia.org/wiki/Mbaramo"]),
    ("capital", "Tolinvara", "Philippine", "province", "PASS", "replacement", ["en.wikipedia.org/wiki/Provinces_of_the_Philippines"]),
    ("capital", "Orvanja", "Croatian", "county", "PASS", "replacement; nearest: Orljavac, Oraovac (villages, different names)", ["en.wikipedia.org/wiki/Orljavac"]),
    ("capital", "Nkhalira", "Malawian", "region", "DROP-a", "second pass: a real village in Nsanje District, Malawi", ["faceofmalawi.com/2026/05/17/man-arrested-for-allegedly-killing-friend-over-headsets-in-nsanje/"]),
    ("capital", "Vrandelsk", "Russian", "oblast", "PASS", "replacement (second pass); bare query hits only a personal name, Vrandel", ["en.wikipedia.org/wiki/Veliky_Vrag,_Kstovsky_District,_Nizhny_Novgorod_Oblast"]),
    ("capital", "Quevarra", "Argentine", "province", "PASS", "replacement (second pass); bare query hits only a personal name (Quevarra Moten); near Quevar, a Salta mountain (different type)", ["summitpost.org/nevado-queva/726324"]),
    ("novel", "The Lantern at Harrowgate", "Charles Dickens", None, "PASS", "", ["en.wikipedia.org/wiki/Dickens's_London"]),
    ("novel", "A Season of Glass", "Edith Wharton", None, "DROP-a", "second pass: real novels with the exact title (John Caulfield, crime; J. Mullican, fantasy) and a Donna Dewberry painting book; first found by Mark's Gemini review", ["amazon.in/Season-Glass-John-Caulfield/dp/1625261462"]),
    ("novel", "The Cartographer's Widow", "Thomas Hardy", None, "DROP-a", "second pass: a real mystery novel with the exact title (Fiona Briarwood)", ["amazon.com/Cartographers-Widow-Suspenseful-Mystery-Secrets-ebook/dp/B0GZ7Q1PN3"]),
    ("novel", "Winter at Halbrook", "Anthony Trollope", None, "PASS", "", ["goodreads.com/author/show/20524.Anthony_Trollope"]),
    ("novel", "The Salt Orchard", "John Steinbeck", None, "DROP-a", "second pass: 'Salt Orchard' is a real band (Dayton, Ohio) and a Cape Town development", ["saltorchard.bandcamp.com"]),
    ("novel", "Evening in Varenne", "Virginia Woolf", None, "PASS", "nearest: That Night in Varennes (1982 film; Catherine Rihoit's novel La nuit de Varennes) -- different words", ["en.wikipedia.org/wiki/Virginia_Woolf_bibliography"]),
    ("novel", "The Brass Meridian", "Jules Verne", None, "DROP-b", "too close to Verne's real 'Meridiana' (a meridian-measuring novel); the search summary itself conflated them", ["librivox.org/meridiana-by-jules-verne"]),
    ("novel", "A House on Tollgate Hill", "Elizabeth Gaskell", None, "PASS", "", ["en.wikipedia.org/wiki/84_Plymouth_Grove"]),
    ("novel", "The Last Ferry to Orme", "Graham Greene", None, "PASS", "", ["en.wikipedia.org/wiki/Graham_Greene_bibliography"]),
    ("novel", "Daughters of the Weir", "George Eliot", None, "PASS", "", ["georgeeliotarchive.org/items/show/5297"]),
    ("novel", "The Ninth Lamplighter", "Wilkie Collins", None, "PASS", "", ["gutenberg.org/files/58089/58089-h/58089-h.htm"]),
    ("novel", "The Pembury Letters", "E. M. Forster", None, "PASS", "replacement (second pass); nearest: Pembury, a Kent village", ["en.wikipedia.org/wiki/Pembury"]),
    ("novel", "Harvest at Coldmere", "Willa Cather", None, "PASS", "replacement (second pass)", ["en.wikipedia.org/wiki/Harvest_(Crace_novel)"]),
    ("novel", "A Harbour in Winter", "Joseph Conrad", None, "PASS", "replacement (second pass); nearest: Winter Harbour (places), Harbour (Lindqvist novel)", ["en.wikipedia.org/wiki/Winter_Harbour"]),
    ("novel", "The Leightons of Fernhill", "Henry James", None, "SPARE", "passes bare and typed queries; not needed", ["en.wikipedia.org/wiki/Fernhill"]),
    ("novel", "Mrs. Arbery's Journey", "Arnold Bennett", None, "DROP-c", "no exact hit, but search ties the surname to a real family's tragedy (Ahmaud Arbery); not used", []),
    ("opera", "Il pellegrino di Candia", None, None, "PASS", "", ["it.wikipedia.org/wiki/Roberto_De_Candia"]),
    ("opera", "La vedova di Smirne", None, None, "PASS", "nearest: Goldoni's play L'impresario delle Smirne", ["it.wikipedia.org/wiki/L'impresario_delle_Smirne"]),
    ("opera", "Der Glasbläser", None, None, "DROP-a", "a brass-band piece has the exact title", ["blasmusik-shop.de/Der-Glasblaeser"]),
    ("opera", "Rosamunda d'Aquileia", None, None, "PASS", "nearest: Rosmonda d'Inghilterra (Donizetti)", ["en.wikipedia.org/wiki/Rosmonda_d'Inghilterra"]),
    ("opera", "Le Fiancé de Lorient", None, None, "PASS", "", ["lorient.bzh/theatredelorient"]),
    ("opera", "Il conte di Trebisonda", None, None, "PASS", "", ["edblogs.columbia.edu/worldepics/rinaldo-imperatore-di-trebisonda"]),
    ("opera", "La figlia del faro", None, None, "PASS", "", ["en.wikipedia.org/wiki/La_figlia_del_mago"]),
    ("opera", "Der Fährmann von Rügen", None, None, "PASS", "", ["de.wikipedia.org/wiki/F%C3%A4hrmann"]),
    ("opera", "Die Seidenweberin", None, None, "DROP-a", "a 2007 novel has the exact title", ["histo-couch.de/titel/604-die-seidenweberin"]),
    ("opera", "Ermengarda di Susa", None, None, "DROP-b", "a real opera 'Ermengarda' (Buzzi, Trieste 1855)", ["loc.gov/item/2010658372"]),
    ("opera", "Les Noces de Ker-Morvan", None, None, "PASS", "", ["en.wikipedia.org/wiki/Les_noces_de_Jeannette"]),
    ("opera", "La sposa di Tangeri", None, None, "PASS", "", ["en.wikipedia.org/wiki/La_sposa_fedele"]),
    ("opera", "Il notaio di Ferrara", None, None, "PASS", "", ["en.wikipedia.org/wiki/Teatro_Comunale_(Ferrara)"]),
    ("opera", "Le Moulin de Kerbriant", None, None, "SPARE", "passes; Kerbriant is a real manor (a real place, an invented opera)", ["brest.fr/manoir-de-kerbriant"]),
    ("university", "Northbridge State University", "the United States", None, "DROP-b", "Northbridge University (Puerto Rico, renamed 2026)", ["en.wikipedia.org/wiki/Northbridge_University"]),
    ("university", "Aldersgate University", "the United Kingdom", None, "DROP-a", "Aldersgate University exists (Philippines)", ["educations.com/institutions/aldersgate-university"]),
    ("university", "Rivermont Polytechnic University", "the United States", None, "PASS", "nearest: Rivermont Collegiate (a K-12 school)", ["en.wikipedia.org/wiki/Rivermont_Collegiate"]),
    ("university", "the University of Carrowmore", "Ireland", None, "PASS", "", ["en.wikipedia.org/wiki/Carrowmore"]),
    ("university", "Hollins Ridge University", "the United States", None, "DROP-b", "Hollins University (word added)", ["en.wikipedia.org/wiki/Hollins_University"]),
    ("university", "the Kellerman Institute of Technology", "the United States", None, "PASS", "", ["facebook.com/KellermanICTPty"]),
    ("university", "the Université de Haute-Garonne", "France", None, "DROP-b", "reads as 'a university in Haute-Garonne' (Toulouse, 1229): conflation risk", ["demarchesadministratives.fr/universite/haute-garonne-31"]),
    ("university", "the Universität Lahnstein", "Germany", None, "PASS", "", ["en.wikipedia.org/wiki/Lahnstein"]),
    ("university", "the Universidad Técnica de Montalvo", "Ecuador", None, "PASS", "nearest: Instituto Superior Tecnologico Juan Montalvo (different name/type)", ["universidades.ec/universidades/instituto-superior-tecnologico-juan-montalvo"]),
    ("university", "Charnwood Metropolitan University", "the United Kingdom", None, "PASS", "", ["en.wikipedia.org/wiki/Charnwood_College"]),
    ("university", "the University of Port Keswick", "Australia", None, "PASS", "", ["en.wikipedia.org/wiki/Keswick,_South_Australia"]),
    ("university", "the Hochschule Rabenau", "Germany", None, "PASS", "", ["aubi-plus.de/duales-studium/ort/rabenau-hessen-38098"]),
    ("university", "the Instituto Politécnico de Valdemora", "Spain", None, "PASS", "nearest: Valdemoro (a town)", ["en.wikipedia.org/wiki/Valdemoro"]),
    ("university", "Brackendale University", "Canada", None, "PASS", "", ["en.wikipedia.org/wiki/Brackendale,_British_Columbia"]),
]


def question(t, name, ctx, kind):
    return {"capital": CAPITAL_Q.format(ctx=ctx, kind=kind, name=name), "novel": NOVEL_Q.format(name=name, ctx=ctx),
            "opera": OPERA_Q.format(name=name), "university": UNIV_Q.format(name=name, ctx=ctx)}[t]


def entity_name(t, name):
    return name[4:] if name.startswith("the ") else name


if __name__ == "__main__":
    out = HERE / "fakes_checks.jsonl"
    prior = {r["name"]: r for r in map(json.loads, open(out))} if out.exists() else {}   # keep wd_labels.py results
    WQ = json.load(open(HERE / "web_queries.json"))
    with open(out, "w") as f:
        for t, name, ctx, kind, v, why, web in C:
            n = entity_name(t, name)
            row = {"template": t, "name": n, "question": question(t, name, ctx, kind), "web_verdict": v, "reason": why,
                   "web_top": web,
                   "web_checked": "2026-09-26 WebSearch: context query, then bare exact-phrase; novels also typed"}
            row.update({k: prior[n][k] for k in ("wikidata_exact", "wikidata_checked") if k in prior.get(n, {})})
            row["web_queries"] = WQ.get(n, [])
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    from collections import Counter
    print(Counter((t, v) for t, _, _, _, v, _, _ in C))
