# Compendium: what we know about the things we touch

Ground truth from experience, for every agent and for Mark. Open the page for a thing BEFORE you touch it: a machine
before you run on it, a model before you serve or score it, the measurement page before you design a test.

## How this differs from its neighbours

- `data/receipts/INDEX.md` is the catalogue: one row per receipt, keyed by mechanism, never revised. Use it to ask
  "has anyone measured this?" (`tools/ledger_precheck.py` greps it).
- `data/receipts/FAILURE_MODES.md` is how we got things wrong, as incidents.
- **The compendium is keyed by the thing you are about to touch and holds the CURRENT best statement about it.** When a
  later receipt changes a statement, the old line is struck and the new one cites the new receipt. It is short on
  purpose: a page is read in a minute.
- Rules (what to ask first, what never to commit, how to share hardware) live in `AGENTS.md` and are not repeated
  here. Live serving settings live in `STATUS.md`.

## Pages

| page | covers |
|---|---|
| `measurement.md` | lessons that changed a published number or came back more than once |
| `machines/194.md` | the four-P100 test host |
| `models/qwen3.8-27b.md` | the 27B that anchors the scorecard and serves the daily |

Wanted next: `machines/73.md`, `machines/desktop-9070xt.md`, `engines/` (llama.cpp upstream, buun, the sm_60 builds),
more model pages as models earn them.

## Line rules

1. **One line, four parts:** the claim; its scope (which file and quant, which build, which settings, how many items);
   the date it was measured; the receipt. Form:
   `- **Claim.** Scope. (measured 2026-MM-DD; `path/to/receipt.md`)`
2. **No receipt, no line.** Cite a path under `data/receipts/`, another file in this repository, or an incident id in
   `FAILURE_MODES.md` (`AFM-26`). Never cite an INDEX line number (they shift) or an agent's memory.
3. **A number is copied from its receipt, not from memory or from an index row.** Open the receipt.
4. **Never delete; strike.** `- ~~old claim~~ superseded 2026-MM-DD: new claim. (...)` The struck text stays so a
   reader who remembers the old claim can see it was replaced.
5. **Experience without a receipt** goes under "Seen, not yet measured" at the foot of a page, with who saw it and
   when. Those lines are leads for a test, not facts to build on.
6. **A page states what holds now.** If two receipts disagree and neither supersedes the other, write both and say so.
7. **Add a line when a receipt lands and it would change what the next person does.** Most receipts add nothing here;
   they still get their INDEX row.
8. **Public repository:** no private or client material, no benchmark items or answers, no addresses, keys or home
   paths.

`tools/compendium_check.py` checks rules 1 and 2 mechanically (every line has a date and a citation that exists).
