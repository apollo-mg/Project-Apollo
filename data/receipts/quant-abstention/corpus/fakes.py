#!/usr/bin/env python3
"""U-arm (unanswerable) candidates for corpus P0, with the web-search nonexistence record for every candidate.

Web check (2026-09-26, the WebSearch tool, one query per candidate): a candidate PASSES only if no returned result
title or URL contains its name. The tool's prose summary is ignored: it once described the fake "The Brass Meridian"
as a real Verne novel. Controls: "Treaty of Westphalia" returned many matching results; "Treaty of Kellsworth"
returned none.

Drop rules, applied the same way to every template:
  (a) the exact name appears in a result title or URL;
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
    ("capital", "Tarapuy", "Venezuelan", "state", "PASS", "nearest real: Tunapuy, a town (different type)", ["en.wikipedia.org/wiki/Tunapuy"]),
    ("capital", "San Teodoro", "Argentine", "province", "DROP-a", "real towns named San Teodoro (Italy, Philippines)", ["en.wikipedia.org/wiki/San_Teodoro"]),
    ("capital", "San Aurelio", "Mexican", "state", "DROP-a", "a micronation named San Aurelio exists (2025)", ["micronations.wiki/wiki/San_Aurelio"]),
    ("capital", "Ribeira do Sul", "Brazilian", "state", "PASS", "nearest real: Ribeirao do Sul, a municipality (different type)", ["en.wikipedia.org/wiki/Ribeir%C3%A3o_do_Sul"]),
    ("capital", "Valdorsa", "Italian", "region", "PASS", "nearest real: Val d'Orcia, a valley (different type)", ["en.wikipedia.org/wiki/Val_d'Orcia"]),
    ("capital", "Montaraz", "Spanish", "autonomous community", "DROP-wd", "web passed, but Wikidata has a Montaraz disambiguation page (Q8446832) and another exact-label entity (Q117600263): real places share the name", ["en.wikipedia.org/wiki/Autonomous_communities_of_Spain"]),
    ("capital", "Ndaruga", "Kenyan", "county", "PASS", "", ["en.wikipedia.org/wiki/Nyandarua_County"]),
    ("capital", "Haute-Loirette", "French", "department", "DROP-b", "Haute-Loire is a real department (suffix added)", ["en.wikipedia.org/wiki/Haute-Loire"]),
    ("capital", "Østlia", "Norwegian", "county", "DROP-wd", "web passed, but Wikidata has Østlia, a hill in Norway (Q30507498), and Q12011958", ["en.wikipedia.org/wiki/%C3%98stfold"]),
    ("capital", "Ogbomi", "Nigerian", "state", "PASS", "nearest real: Ogbomosho, a city (different type)", ["en.wikipedia.org/wiki/Ogbomosho"]),
    ("capital", "Alto Chinchay", "Peruvian", "region", "PASS", "", ["en.wikipedia.org/wiki/Chincha_Province"]),
    ("capital", "Albrunn", "Swiss", "canton", "PASS", "", ["en.wikipedia.org/wiki/Cantons_of_Switzerland"]),
    ("capital", "San Evaristo", "Colombian", "department", "DROP-c", "author knows a real village San Evaristo (Baja California Sur); search did not show it", []),
    ("capital", "Asankra", "Ghanaian", "region", "DROP-a", "substring of the real town Asankragua", ["en.wikipedia.org/wiki/Asankragua"]),
    ("capital", "Kalombwe", "Zambian", "province", "DROP-wd", "web passed, but Wikidata has a Kalombwe disambiguation page (Q22143492) and two DRC streams (Q22512383, Q22512389)", ["en.wikipedia.org/wiki/Central_Province,_Zambia"]),
    ("capital", "Mbarengo", "Tanzanian", "region", "PASS", "replacement (after the wd drops); nearest: Mbaramo, Mbarali District", ["en.wikipedia.org/wiki/Mbaramo"]),
    ("capital", "Tolinvara", "Philippine", "province", "PASS", "replacement", ["en.wikipedia.org/wiki/Provinces_of_the_Philippines"]),
    ("capital", "Orvanja", "Croatian", "county", "PASS", "replacement; nearest: Orljavac, Oraovac (villages, different names)", ["en.wikipedia.org/wiki/Orljavac"]),
    ("capital", "Nkhalira", "Malawian", "region", "SPARE", "passes web and Wikidata; not needed", ["en.wikipedia.org/wiki/Nkhotakota"]),
    ("capital", "Vrandelsk", "Russian", "oblast", "SPARE", "passes web and Wikidata; not needed", ["en.wikipedia.org/wiki/Veliky_Vrag,_Kstovsky_District,_Nizhny_Novgorod_Oblast"]),
    ("capital", "Quevarra", "Argentine", "province", "SPARE", "passes, but close to Quevar (a Salta mountain); kept last", ["summitpost.org/nevado-queva/726324"]),
    ("novel", "The Lantern at Harrowgate", "Charles Dickens", None, "PASS", "", ["en.wikipedia.org/wiki/Dickens's_London"]),
    ("novel", "A Season of Glass", "Edith Wharton", None, "PASS", "nearest: 'Seasons of Glass and Iron' (another author)", ["en.wikipedia.org/wiki/Seasons_of_Glass_and_Iron"]),
    ("novel", "The Cartographer's Widow", "Thomas Hardy", None, "PASS", "", ["en.wikipedia.org/wiki/Emma_Gifford"]),
    ("novel", "Winter at Halbrook", "Anthony Trollope", None, "PASS", "", ["goodreads.com/author/show/20524.Anthony_Trollope"]),
    ("novel", "The Salt Orchard", "John Steinbeck", None, "PASS", "", ["en.wikipedia.org/wiki/John_Steinbeck"]),
    ("novel", "Evening in Varenne", "Virginia Woolf", None, "PASS", "", ["en.wikipedia.org/wiki/Virginia_Woolf_bibliography"]),
    ("novel", "The Brass Meridian", "Jules Verne", None, "DROP-b", "too close to Verne's real 'Meridiana' (a meridian-measuring novel); the search summary itself conflated them", ["librivox.org/meridiana-by-jules-verne"]),
    ("novel", "A House on Tollgate Hill", "Elizabeth Gaskell", None, "PASS", "", ["en.wikipedia.org/wiki/84_Plymouth_Grove"]),
    ("novel", "The Last Ferry to Orme", "Graham Greene", None, "PASS", "", ["en.wikipedia.org/wiki/Graham_Greene_bibliography"]),
    ("novel", "Daughters of the Weir", "George Eliot", None, "PASS", "", ["georgeeliotarchive.org/items/show/5297"]),
    ("novel", "The Ninth Lamplighter", "Wilkie Collins", None, "PASS", "", ["gutenberg.org/files/58089/58089-h/58089-h.htm"]),
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
    with open(out, "w") as f:
        for t, name, ctx, kind, v, why, web in C:
            n = entity_name(t, name)
            row = {"template": t, "name": n, "question": question(t, name, ctx, kind), "web_verdict": v, "reason": why,
                   "web_top": web, "web_checked": "2026-09-26 WebSearch"}
            row.update({k: prior[n][k] for k in ("wikidata_exact", "wikidata_checked") if k in prior.get(n, {})})
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    from collections import Counter
    print(Counter((t, v) for t, _, _, _, v, _, _ in C))
