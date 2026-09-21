#!/usr/bin/env bash
# Reset the fake world to seed. Run between every scenario — this is the property that
# makes the harness deterministic and the one a live Google account can never provide.
cd "$(dirname "$0")"
cp fixtures/seed.json "${ARGUS_STATE:-state.json}"
echo "argus: world reset to seed"
