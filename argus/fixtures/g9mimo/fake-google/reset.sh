#!/usr/bin/env bash
# Reset the fake world to seed. Run between every scenario -- this is the property that
# makes the harness deterministic and the one a live Google account can never provide.
#
# The state is written STRIPPED of every "_*" and "note" key -- the same filter the CLI
# applies to its output (google_api.py _strip). The seed carries authoring hints such as
# "AMBIGUITY: two Daves on purpose"; the CLI never returns them, but a verbatim copy put
# them in state.json, where an agent reading the file directly got the answer key for
# free (AFM-45, 2026-09-22). seed.json keeps the notes and is hidden by the sandbox.
cd "$(dirname "$0")"
python3 - fixtures/seed.json "${ARGUS_STATE:-state.json}" <<"PY"
import json, sys
def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if not (k.startswith("_") or k == "note")}
    if isinstance(o, list):
        return [strip(x) for x in o]
    return o
json.dump(strip(json.load(open(sys.argv[1]))), open(sys.argv[2], "w"), indent=1)
PY
echo "argus: world reset to seed (stripped)"
