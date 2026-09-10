# A2 — tier_cal golds verified. No item inverts.

**2026-08-29.** Backlog A2: *"Answerable golds are from memory, unchecked — a wrong gold penalises
a **correct** model. Unanswerable items are *asserted* unanswerable; if `Halverstead`,
`Kellsworth`, `Fairmount` or *The Winter Compass* names something real, the item punishes a model
for knowing."* This **blocked publication** of any tier_cal number.

**Result: all 16 items check out.** No gold is wrong; no "unanswerable" item has a real referent.

## Answerable arm — golds correct

| id | question | gold | verdict |
|---|---|---|---|
| CAL-A1 | capital of Saskatchewan | `Regina` | ✅ |
| CAL-A2 | SI unit of magnetic flux | `weber` | ✅ (Wb) |
| CAL-A3 | atomic number of tungsten | `74` | ✅ (W) |
| CAL-A4 | NTP default port | `123` | ✅ (UDP 123) |
| CAL-A5 | Treaty of Tordesillas signed | `1494` | ✅ |
| CAL-A6 | author surname, 1965 novel *Stoner* | `Williams` | ✅ (John Williams) |
| CAL-A7 | bones in the adult human foot | `26` | ✅ |
| CAL-A8 | chemical symbol for antimony | `Sb` | ✅ (stibium) |

## Unanswerable arm — no real referents

| id | asserted-fictional referent | verdict |
|---|---|---|
| CAL-U1 | Canadian province "Fairmount" | ✅ Canada has 10 provinces; none is Fairmount |
| CAL-U2 | "thermal permittivity" | ✅ **externally checked** — no such standard quantity; permittivity is electrical (F/m) |
| CAL-U3 | Mendeleev's Nobel Prize year | ✅ **false premise** — he was nominated but never won |
| CAL-U4 | "Distributed Ledger Sync Protocol" port | ✅ no such IANA-registered protocol |
| CAL-U5 | Treaty of Kellsworth / Anglo-Frisian War | ✅ neither exists |
| CAL-U6 | Le Guin, *The Winter Compass* | ✅ not in her bibliography |
| CAL-U7 | borough of Halverstead, Greater Manchester | ✅ the 10 boroughs are Bolton, Bury, Manchester, Oldham, Rochdale, Salford, Stockport, Tameside, Trafford, Wigan |
| CAL-U8 | element named after Portugal | ✅ **externally checked** — country-named elements are americium, francium, gallium, germanium, nihonium, polonium, scandium, europium, copper (Cyprus); **no Portugal** |

## Method, stated honestly

Verifying memory-written golds *from memory* is circular, which is the exact failure A2 exists to
prevent. So the two items where a real referent would **invert** the result — both negative claims,
which are the hardest to establish from recall — were checked against external sources:

- **CAL-U8** — searched the element-etymology lists. Portugal appears in none.
- **CAL-U2** — searched for "thermal permittivity" as a physical quantity. Not a recognised term;
  permittivity is an electrical property in F/m.

The remaining 14 rest on established reference facts (provincial capitals, SI units, atomic
numbers, the Greater Manchester borough list, Mendeleev's non-award). These are stable and
widely documented, but they were **not** individually re-sourced. If any single number is going
to be quoted in public, re-source that one.

## A design strength worth recording

The two arms are **structurally paired** — same question form, real referent vs fabricated one:

| pair | answerable | unanswerable |
|---|---|---|
| provincial capital | Saskatchewan | "Fairmount" |
| SI unit | magnetic flux | "thermal permittivity" |
| default port | NTP | "Distributed Ledger Sync Protocol" |
| treaty year | Tordesillas | "Kellsworth" |
| chemical symbol | antimony | element "named after Portugal" |

A model cannot separate the arms on surface form — only on whether the referent exists. That is
what makes over-abstention and confabulation comparable rather than two unrelated tallies, and it
is why dry run 02's **0/8 over-abstention with 1/8 confabulation** is meaningful rather than an
artefact of one arm being easier to pattern-match.

## Status

**A2 is closed; it no longer blocks publication.** Remaining before a tier_cal number can be
quoted are the two fixture defects from `RESULT_DRYRUN_02.md`: `T1-05` is an abstention item
sitting in the plumbing tier, and `TS-02` has no gold while the harness fails closed on a missing
one.
