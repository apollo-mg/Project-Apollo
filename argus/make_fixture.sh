#!/usr/bin/env bash
# Clone an isolated Argus fixture so arms can run in PARALLEL.
#
# Every concurrent arm needs its own: fake-google world (state.json is ONE file -- two
# runs against it corrupt each other's audit and call logs), HERMES_HOME (skills + session
# db), gateway port, and a SKILL.md baked with THIS fixture's backend path. Miss the last
# one and both fixtures silently share a world, which looks like nondeterminism.
set -euo pipefail   # pipefail: a failure piped into `tail` must NOT report success
NAME="${1:?usage: make_fixture.sh <name> <gateway-port>}"
PORT="${2:?usage: make_fixture.sh <name> <gateway-port>}"
ROOT=$(cd "$(dirname "$0")" && pwd)
F="$ROOT/fixtures/$NAME"
[ -e "$F" ] && { echo "fixture $NAME already exists at $F"; exit 1; }

mkdir -p "$F"
cp -r "$ROOT/fake-google" "$F/fake-google"
rm -f "$F/fake-google/state.json"
mkdir -p "$F/agent-home/no-bundled-skills"
cp "$ROOT/agent-home/config.yaml" "$F/agent-home/config.yaml"
cp "$ROOT/agent-home/.env" "$F/agent-home/.env" 2>/dev/null || true
sed -i "s/port: [0-9]\+/port: $PORT/" "$F/agent-home/config.yaml"
sed -i "s|/mnt/TG_2TB/Projects/Apollo/argus/fake-google|$F/fake-google|g" "$F/fake-google/reset.sh" 2>/dev/null || true

PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
# Anchor the world's dates to TODAY. seed.json hardcodes 2026-08-27; run it on any other day
# and time-relative scenarios ("clear my afternoon") address an empty calendar, so the agent
# scores clean because it CANNOT act, not because it chose not to. That silently voided a
# four-arm n=12 comparison. Rebase before reset.sh, which copies seed -> state.
"$PY" "$ROOT/rebase_seed.py" "$F/fake-google/fixtures/seed.json" --force

"$PY" "$ROOT/install_skill.py" \
    --hermes-home "$F/agent-home" --gapi "$F/fake-google/scripts/google_api.py"
"$F/fake-google/reset.sh" >/dev/null 2>&1 || (cd "$F/fake-google" && ./reset.sh)

# verify rather than assume: the skill must exist AND point at THIS fixture's backend
SK="$F/agent-home/skills/google/google-workspace/SKILL.md"
[ -f "$SK" ] || { echo "FAIL: skill not installed at $SK"; exit 1; }
grep -q "$F/fake-google" "$SK" || { echo "FAIL: SKILL.md does not reference this fixture's backend"; exit 1; }
echo "fixture '$NAME' ready (skill verified)"
echo "  world       $F/fake-google"
echo "  HERMES_HOME $F/agent-home"
echo "  gateway     127.0.0.1:$PORT"
echo
echo "start its gateway:"
echo "  cd /mnt/TG_2TB/AI/hermes-go && HERMES_HOME=$F/agent-home API_SERVER_KEY=argus-local-test-key-0123456789 \\"
echo "    API_SERVER_PORT=$PORT HERMES_BUNDLED_SKILLS=$F/agent-home/no-bundled-skills \\"
echo "    setsid nohup .venv/bin/python scripts/hermes-gateway > $F/gateway.log 2>&1 < /dev/null & disown"
echo "run an arm against it:"
echo "  ./driver.py --transport gateway --base http://127.0.0.1:$PORT \\"
echo "    --fake-root $F/fake-google --out runs/<arm>.jsonl"
