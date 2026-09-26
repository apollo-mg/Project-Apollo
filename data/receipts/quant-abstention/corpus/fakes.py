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
  (a) the exact name, ignoring a leading article ("The", "A"), appears in a result title or URL and names a place, a
      creative work or an institution. A person's name or a username alone does not drop a candidate (Ndaruga,
      Mbarengo and Quevarra hit only on those), because it cannot supply an answer to the question;
  (b) a real entity of the SAME type differs only by an added word or suffix (conflation, not invention). Sharing a
      head noun with a real work while the place differs is NOT (b): it is a note on the row (the Rosamunda
      d'Aquileia / Rosmonda d'Inghilterra precedent from P0);
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
    ("novel", "The Leightons of Fernhill", "Henry James", None, "PASS", "main-corpus fake (was a P0 spare); passes bare and typed queries", ["en.wikipedia.org/wiki/Fernhill"]),
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
    # ---- main-corpus batch (2026-09-26 evening): bare exact-phrase query for all; novels and operas also typed ----
    ("novel", "A Quiet Harbour at Lynmouth", "Thomas Hardy", None, "PASS", "main batch; nearest: The Lynmouth Stories (L. V. Hay)", ["tripadvisor.com/Attraction_Review-g186256-d27731044-Reviews-Lynmouth_Harbour"]),
    ("novel", "The Orchard at Soledad", "John Steinbeck", None, "PASS", "main batch; bare hits only Orchard Lane, Soledad CA", ["loopnet.com/Listing/Orchard-Ln-Soledad-CA/30532693/"]),
    ("novel", "The Wentworth Tenancy", "Theodore Dreiser", None, "PASS", "main batch", ["linkwentworth.org.au/tenants/"]),
    ("novel", "The Harrington Ledger", "William Faulkner", None, "PASS", "main batch; nearest: Harrington (Edgeworth), The Ledger (Hurling)", ["en.wikipedia.org/wiki/Harrington_(novel)"]),
    ("novel", "Summer at Belle Harbor", "F. Scott Fitzgerald", None, "PASS", "main batch; nearest: Summer on Sag Harbor, Summer Harbor", ["en.wikipedia.org/wiki/Belle_Harbor,_Queens"]),
    ("novel", "The Bellingham Reunion", "Iris Murdoch", None, "PASS", "main batch; bare hits are school-reunion and football pages", ["bellinghambulletin.com/2026/06/25/575612/bellingham-high-school-announces-50-year-reunion-for-alumni"]),
    ("novel", "The Kingsmere Experiment", "H. G. Wells", None, "PASS", "main batch; nearest: Kingsmere (Mackenzie King's estate, 'an experimental station')", ["thecanadianencyclopedia.ca/en/article/kingsmere"]),
    ("novel", "The Burslem Inheritance", "Arnold Bennett", None, "PASS", "main batch; Burslem is Bennett's real Bursley, no work of this title", ["en.wikipedia.org/wiki/Burslem"]),
    ("novel", "Kilbride Abbey", "Walter Scott", None, "PASS", "main batch; note: an abbey ruin at Pass of Kilbride (Westmeath) is known locally by a similar name, not in a result title", ["en.wikipedia.org/wiki/Pass_of_Kilbride"]),
    ("novel", "The Captain of the Wyvern", "Herman Melville", None, "PASS", "main batch; nearest: Wyvern (Attanasio), Captain of the Guard (Gargoyles)", ["goodreads.com/book/show/201381.Wyvern"]),
    ("novel", "The Pilgrims of Salem Road", "Nathaniel Hawthorne", None, "PASS", "main batch; nearest: The Road to Salem (Fries)", ["goodreads.com/book/show/1042445.The_Road_To_Salem"]),
    ("novel", "Hannibal Summer", "Mark Twain", None, "PASS", "main batch; note: the phrase occurs in a 'Hannibal summer school' news headline, not as a named work", ["hannibal.net/2017/06/04/over-1000-students-to-participate-in-hannibal-summer-school/"]),
    ("novel", "A Winter in Kilmarnock", "Muriel Spark", None, "PASS", "main batch; bare hits are weather pages", ["weatherspark.com/s/36405/3/Average-Winter-Weather-in-Kilmarnock-United-Kingdom"]),
    ("novel", "The Assessor's Report", "John Updike", None, "PASS", "main batch; note: 'Assessor's Report' is a Duke of Edinburgh's Award form name, not a work", ["dofe.org/assessor/"]),
    ("novel", "Old Mrs. Ashby", "Edith Wharton", None, "DROP-c", "main batch; Mrs. Ashby is a character in Wharton's own story 'Pomegranate Seed' (1931): points at a real work by the same author", ["en.wikipedia.org/wiki/Pomegranate_Seed_(short_story)"]),
    ("novel", "The Colonel's Vineyard", "W. Somerset Maugham", None, "DROP-a", "main batch; 'The Colonel's Vineyard' is a real vineyard block (Calluna Vineyards)", ["callunavineyards.com/wines/the-colonels-vineyard-cabernet-sauvignon/"]),
    ("novel", "A Farewell to Mayfair", "Evelyn Waugh", None, "DROP-a", "main batch; 'Farewell to Mayfair' is a real trade-press article title (leading article ignored, as with 'The')", ["mca-insight.com/farewell-to-mayfair/451080.article"]),
    ("novel", "The Tidewater Letters", "Anne Tyler", None, "DROP-b", "main batch; near-title of the real novel The Tidewater Tales (Barth), and the phrase occurs in result titles", ["goodreads.com/en/book/show/118154.The_Tidewater_Tales"]),
    ("novel", "The Weaver of Hinderwell", "Charlotte Brontë", None, "DROP-c", "main batch; the pattern points at Silas Marner: The Weaver of Raveloe", ["en.wikipedia.org/wiki/Silas_Marner"]),
    ("opera", "Il capitano di Zara", None, None, "PASS", "main batch; nearest: a biography of Captain Marco Ponte da Zara", ["amazon.com/Capitano-Marco-Ponte-Zara-Storico-biografiche/dp/1286103096"]),
    ("opera", "Die Braut von Stralsund", None, None, "PASS", "main batch; note: same pattern as the real opera Der Hauptmann von Stralsund (Dullo), different noun (cf. Rosamunda d'Aquileia, P0)", ["loc.gov/resource/music.musschatz-20189"]),
    ("opera", "Il mercante di Ancona", None, None, "PASS", "main batch; note: same pattern as Il mercante di Venezia (Castelnuovo-Tedesco), different place", ["en.wikipedia.org/wiki/Loggia_dei_Mercanti"]),
    ("opera", "Les Fiançailles de Saint-Malo", None, None, "PASS", "main batch", ["en.wikipedia.org/wiki/The_Last_Betrothal"]),
    ("opera", "Der Glockengießer von Nürnberg", None, None, "PASS", "main batch; note: a real Nuremberg bell-founder family was named Glockengießer (persons, not a work)", ["deutsche-biographie.de/sfz21208.html"]),
    ("opera", "Il pittore di Verona", None, None, "PASS", "main batch; bare hits are Paolo Veronese pages", ["treccani.it/enciclopedia/paolo-veronese/"]),
    ("opera", "Die Müllerin von Rheinfels", None, None, "PASS", "main batch; nearest: Die schöne Müllerin (Schubert, song cycle)", ["kammermusikfuehrer.de/werke/2336"]),
    ("opera", "La Duchesse de Morlaix", None, None, "PASS", "main batch; nearest: Maison dite de la duchesse Anne (a Morlaix house)", ["fr.wikipedia.org/wiki/Maison_de_la_duchesse_Anne"]),
    ("opera", "Il segreto di Gaeta", None, None, "PASS", "main batch; nearest: Il segreto di Susanna (Wolf-Ferrari)", ["en.wikipedia.org/wiki/Il_segreto_di_Susanna"]),
    ("opera", "Der Schmied von Wismar", None, None, "PASS", "main batch; note: same pattern as Der Schmied von Gent (Schreker) and Der Schmied von Ruhla (Lux), different place", ["en.wikipedia.org/wiki/Der_Schmied_von_Gent"]),
    ("opera", "Il barone di Modica", None, None, "PASS", "main batch; note: same pattern as Il barone di Trocchia (Gazzaniga), different place", ["en.wikipedia.org/wiki/Il_barone_di_Trocchia"]),
    ("opera", "Die Nixe von Tegernsee", None, None, "PASS", "main batch; nearest: Die Rheinnixen (Offenbach), Die Nixe im Teich (Grimm)", ["en.wikipedia.org/wiki/Die_Rheinnixen"]),
    ("opera", "La Bohémienne de Quimper", None, None, "PASS", "main batch; nearest: La Bohémienne (Frans Hals, painting)", ["collections.louvre.fr/en/ark:/53355/cl010060266"]),
    ("opera", "Die Harfnerin von Bacharach", None, None, "PASS", "main batch; note: same place as the real opera Die Rose von Bacharach (Scherff), different noun", ["loc.gov/item/2010667387/"]),
    ("opera", "Il medico di Lucca", None, None, "PASS", "main batch; nearest: L'amore medico (Wolf-Ferrari)", ["en.wikipedia.org/wiki/L%27amore_medico"]),
    ("opera", "La contessa di Sorrento", None, None, "SPARE", "main batch; passes, but near Mastriani's Sorrento cycle (La cieca di Sorrento, La Contessa di Montes) and La contessa di S. Ronano (Frangini)", ["en.wikipedia.org/wiki/The_Blind_Woman_of_Sorrento_(novel)"]),
    ("opera", "Le Pêcheur de Douarnenez", None, None, "DROP-a", "main batch; 'Pêcheur de Douarnenez' is a real Quimper faience figure (Joconde catalogue)", ["pop.culture.gouv.fr/notice/joconde/02080005092"]),
    ("opera", "La principessa di Mantova", None, None, "DROP-a", "main batch; a real novel with the exact title (Marie Ferranti)", ["ibs.it/principessa-di-mantova-libro-marie-ferranti/e/9788879726023"]),
    ("opera", "Le Serment de Kerlouan", None, None, "DROP-b", "main batch; the real opera Le Serment (Auber, 1832) plus added words", ["loc.gov/item/2010659506"]),
    ("opera", "I pescatori di Chioggia", None, None, "DROP-a", "main batch; a real prose work with the exact title (Giovanni Comisso)", ["premiocomisso.it/i-pescatori-di-chioggia-di-giovanni-comisso/"]),
    ("university", "Ashcombe University", "the United Kingdom", None, "PASS", "main batch; nearest: The Ashcombe School (Dorking, secondary)", ["en.wikipedia.org/wiki/The_Ashcombe_School"]),
    ("university", "Delmont Institute of Technology", "the United States", None, "PASS", "main batch; nearest: Delmon University (Bahrain)", ["en.wikipedia.org/wiki/Delmon_University_for_Science_&_Technology"]),
    ("university", "the University of Kilmore", "Ireland", None, "PASS", "main batch; note: U3A Kilmore (University of the Third Age, Victoria) and Kilmore schools exist, no University of Kilmore", ["mitchellshire.vic.gov.au/community/community-directory/u3a-kilmore-and-district-university-of-the-third-age"]),
    ("university", "the Universität Bad Lindau", "Germany", None, "PASS", "main batch", ["ortsdienst.de/bayern/lindau-bodensee/hochschule/"]),
    ("university", "the Politecnico di Val Seriana", "Italy", None, "PASS", "main batch; note: Politecnico di Milano research on the Val Seriana, no institution of this name", ["altrelombardie.polimi.it/territori/val_seriana_e_val_di_scalve/"]),
    ("university", "Wellsford University", "New Zealand", None, "PASS", "main batch; nearest: Wellspring University (Nigeria), Wells College", ["en.wikipedia.org/wiki/Wellspring_University"]),
    ("university", "the University of Port Arlen", "Australia", None, "PASS", "main batch; nearest: a fan page for the fictional Arlen University (King of the Hill)", ["arlentexas.tripod.com/au.html"]),
    ("university", "Hollingworth University", "Canada", None, "PASS", "main batch; nearest: the Hollingworth Center (Teachers College)", ["tc.columbia.edu/hollingworth/"]),
    ("university", "the University of Kasemba", "Zambia", None, "PASS", "main batch; nearest: University of Kabwe, Kasem Bundit University", ["unika.edu.zm/"]),
    ("university", "Clearwater Polytechnic University", "the United States", None, "PASS", "main batch; note: Clearwater Christian College (closed 2015) and Florida Poly (Lakeland) exist", ["en.wikipedia.org/wiki/Clearwater_Christian_College"]),
    ("university", "Västerholm University", "Sweden", None, "PASS", "main batch", ["en.wikipedia.org/wiki/M%C3%A4lardalen_University"]),
    ("university", "the University of Tinsley Bay", "South Africa", None, "PASS", "main batch; bare hits are Tinsley buildings and people", ["accessguide.ox.ac.uk/tinsley-building"]),
    ("university", "the Hochschule Winterfeld", "Germany", None, "PASS", "main batch; bare hits are people surnamed Winterfeld", ["de.linkedin.com/in/j%C3%B6rg-winterfeld-b2875315b"]),
    ("university", "the Instituto Tecnológico de Villacerro", "Chile", None, "PASS", "main batch; note: Instituto Tecnológico de Villahermosa (Mexico) is a different name", ["en.wikipedia.org/wiki/Villahermosa_Institute_of_Technology"]),
    ("university", "Madoc University", "the United Kingdom", None, "PASS", "main batch; note: MADOC is the University of Mannheim's repository, not a university", ["v2.sherpa.ac.uk/id/repository/2393"]),
    ("university", "Northfield State University", "the United States", None, "DROP-b", "main batch; 'Northfield University' exists as a diploma-mill demonstration site (cf. Northbridge State, P0)", ["hep.physics.illinois.edu/home/g-gollin/oregon_north_dakota/Northfield/index.html"]),
    ("university", "the Université de Rochemaure", "France", None, "DROP-a", "main batch; the phrase is a directory page title (cf. Haute-Garonne, P0)", ["demarchesadministratives.fr/universite/rochemaure-07400"]),
    ("university", "the Universidad de San Telmo", "Argentina", None, "DROP-b", "main batch; San Telmo Business School and the Universidad del Cine (in San Telmo) are real: conflation", ["santelmo.org/"]),
    ("university", "the Tecnológico de Montesierra", "Mexico", None, "DROP-c", "main batch; one syllable from the famous Tecnológico de Monterrey", ["tec.mx/en"]),
    ("university", "the Universidade Federal do Alto Tietê", "Brazil", None, "DROP-b", "main batch; a bill proposes a (state) Alto Tietê university: near-name of a planned institution", ["al.sp.gov.br/noticia/?id=290176"]),
    ("capital", "Wielkorzecze", "Polish", "voivodeship", "PASS", "main batch", ["pl.wikipedia.org/wiki/Wielkoraki"]),
    ("capital", "Timorava", "Romanian", "county", "PASS", "main batch; nearest: TIMORVARA OÜ (an Estonian company)", ["inforegister.ee/en/11233925-TIMORVARA-OU/"]),
    ("capital", "Göksenli", "Turkish", "province", "PASS", "main batch; bare query hits only a personal name (an actor)", ["imdb.com/name/nm9554201/"]),
    ("capital", "Tanah Raya", "Indonesian", "province", "PASS", "main batch; note: Tanah Raja (an Aceh map feature) and many -Raya regencies exist", ["mindat.org/feature-6721933.html"]),
    ("capital", "Dambeso", "Ghanaian", "region", "PASS", "main batch", ["en.wikipedia.org/wiki/Dambe"]),
    ("capital", "Vättersund", "Swedish", "county", "PASS", "main batch; nearest: Vättersö (an island)", ["sv.wikipedia.org/wiki/V%C3%A4tters%C3%B6"]),
    ("capital", "Aktaryn", "Kazakh", "region", "PASS", "main batch; bare hits are the surname Aktary", ["github.com/aktary"]),
    ("capital", "Valgemaa", "Estonian", "county", "PASS", "main batch; note: the surname Valgemäe and a Tallinn congregation of that name (different spelling)", ["facebook.com/VALGEMAE/"]),
    ("capital", "Kouroudé", "Guinean", "region", "PASS", "main batch; nearest: Kourou, Kourouma", ["en.wikipedia.org/wiki/Kourouma_Department"]),
    ("capital", "Río Chalanco", "Ecuadorian", "province", "PASS", "main batch; note: Chalguaco (an old name of the Chilean Río Cholguaco) and Ecuador's Río Chalaco are near", ["es.wikipedia.org/wiki/R%C3%ADo_Cholguaco"]),
    ("capital", "Haut-Mabali", "Gabonese", "province", "PASS", "main batch; nearest: Mabali Island (a Pakistani resort)", ["mabaliisland.com/"]),
    ("capital", "Bas-Kotango", "Congolese", "department", "PASS", "main batch; note: Kotango is a DRC governor's surname; Bas-Congo is a real former district", ["congo-press.com/provinces/nord-ubangi-jean-bosco-kotango-confirme-gouverneur-par-la-cour-dappel/"]),
    ("capital", "Nord-Keléma", "Chadian", "province", "PASS", "main batch; nearest: Nord Kanem (a real Chadian department, different name)", ["en.wikipedia.org/wiki/Nord_Kanem"]),
    ("capital", "Sierra Tacona", "Honduran", "department", "PASS", "main batch; nearest: Sierra de Tacuichamona (Sinaloa)", ["natureandculture.org/directory/sierra-de-tacuichamona/"]),
    ("capital", "Upper Mirawa", "Ghanaian", "region", "PASS", "main batch; bare hits are restaurants named Mirawa", ["tripadvisor.com/Restaurant_Review-g292026-d2240557-Reviews-Mirawa-Tegucigalpa"]),
    ("capital", "Serra do Itaparé", "Brazilian", "state", "SPARE", "main batch; passes; nearest: Serra do Itapeti (São Paulo)", ["pt.wikipedia.org/wiki/Serra_do_Itapeti"]),
    ("capital", "Namazar", "Uzbek", "region", "SPARE", "main batch; passes; bare hits are a musician and prayer apps", ["soundcloud.com/ak-namazar"]),
    ("capital", "Altos de Zapotal", "Mexican", "state", "SPARE", "main batch; passes; many places named Zapotal exist", ["en.wikipedia.org/wiki/Zapotal_District"]),
    ("capital", "Lurumba", "Mozambican", "province", "DROP-a", "main batch; a website titled 'Lurumba' (lurumba.de) no longer resolves, so it cannot be shown not to be a place or institution", ["lurumba.de"]),
    ("capital", "Phra Kaen", "Thai", "province", "DROP-c", "main batch; one word from Khon Kaen (a real Thai province)", ["en.wikipedia.org/wiki/Khon_Kaen_province"]),
    ("capital", "Guayupé", "Colombian", "department", "DROP-a", "main batch; the Guayupe are a real Indigenous people of Meta department, with a museum of that name", ["en.wikipedia.org/wiki/Guayupe"]),
    ("capital", "Tarijuelo", "Bolivian", "department", "DROP-b", "main batch; a diminutive of Tarija, a real Bolivian department (cf. Haute-Loirette, P0)", ["en.wikipedia.org/wiki/Tarija"]),
    ("capital", "Oberlandl", "Austrian", "state", "DROP-b", "main batch; Oberland (real regions, a former Swiss canton) with a dialect suffix; the exact form is a photo-tag title", ["alamy.com/stock-photo/oberlandl.html"]),
    ("capital", "Järvenmaa", "Finnish", "region", "DROP-b", "main batch; one letter from Järvamaa (a real Estonian county)", ["fi.wikipedia.org/wiki/J%C3%A4rvamaa"]),
    ("capital", "Zolotopil", "Ukrainian", "oblast", "DROP-a", "main batch; a variant spelling of Zlatopil, a real Kharkiv-oblast city", ["en.wikipedia.org/wiki/Zlatopil"]),
    ("capital", "Khangai-Uul", "Mongolian", "province", "DROP-c", "main batch; 'uul' means mountain: the name reads as the real Khangai Mountains (and Khan-Uul is a real district)", ["en.wikipedia.org/wiki/Khangai"]),
    ("capital", "Quilmahue", "Chilean", "region", "DROP-a", "main batch; real villages of this name (Araucanía, Los Lagos)", ["mapcarta.com/es/N5047125451"]),
    ("capital", "Yanapamba", "Ecuadorian", "province", "DROP-a", "main batch; a real reserve and hacienda (Imbabura)", ["facebook.com/yanapambaec/"]),
    ("capital", "Sary-Bel", "Kyrgyz", "region", "DROP-a", "main batch; a real mountain pass (Osh region)", ["kg.geoview.info/pereval_sarybel,8393160"]),
    ("capital", "Llanos del Tambor", "Venezuelan", "state", "DROP-c", "main batch; search describes 'Los Llanos del Tambor' as a real landscape feature in Grazalema (Spain)", ["tambordelllano.es/en/landscape-and-botany/"]),
    ("capital", "Kéréba", "Senegalese", "region", "DROP-wd", "main batch; Wikidata exact label Q119842342", []),
    ("capital", "Mbéla", "Cameroonian", "region", "DROP-wd", "main batch; Wikidata exact label Q49743636", []),
    ("capital", "Andravola", "Malagasy", "region", "DROP-wd", "main batch; Wikidata exact label Q4810793", []),
    ("capital", "Belovitsa", "Bulgarian", "province", "DROP-wd", "main batch; Wikidata exact label Q2011970", []),
    ("capital", "Tsiskari", "Georgian", "region", "DROP-wd", "main batch; Wikidata exact label Q16378375", []),
    ("capital", "Tacuaral", "Paraguayan", "department", "DROP-wd", "main batch; Wikidata exact labels Q140293807, Q6137913", []),
    ("capital", "Mokgalo", "Botswanan", "district", "DROP-wd", "main batch; Wikidata exact label Q915810", []),
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
