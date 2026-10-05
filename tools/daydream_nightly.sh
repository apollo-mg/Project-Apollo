#!/usr/bin/env bash
# Nightly daydream: harvest open threads -> link them to the corpus -> model pass -> morning brief.
# Once a day (apollo-daydream.timer, 04:30), not a resident daemon: the original daydream loop ran every 10 min on
# idle and cost compute for little. Stages: tools/daydream_harvest.py, tools/daydream_links.py, tools/daydream_brief.py.
#
# Like the ledger, the ABSENCE of a brief must be visible: every run writes a heartbeat with an explicit status
# (ok | degraded | error), and the notification says which. Nothing here commits or edits BACKLOG.md; the brief
# proposes, a session or Mark applies.
set -u
ROOT=/mnt/TG_2TB/Projects/Apollo
PY=$ROOT/venv_cachyos/bin/python3
M=$ROOT/data/dev_diaries/morning
D=$(date +%F)
mkdir -p "$M"
LOG=$M/.nightly.log
beat() {   # beat STATUS DETAIL
  "$PY" -c 'import json,sys,time; print(json.dumps({"ts": int(time.time()), "date": sys.argv[1], "status": sys.argv[2], "detail": sys.argv[3]}))' \
    "$D" "$1" "$2" | tee "$M/.heartbeat.json" >> "$M/.beats.jsonl"
}
# -t 0: the brief lands at 04:30, so a normal toast would expire unseen (the first test run's did). Stay until dismissed.
notify() { command -v notify-send >/dev/null 2>&1 && notify-send -a "Apollo daydream" -t 0 "$1" "$2" 2>/dev/null; true; }
# --resume hygiene (2026-10-03; 10-05 erases only the slots this run used). The .73 daily driver saves its slots at the
# next suspend and restores them at every wake (~3.8 ms/token, blocking /health), so the daydream's own chats must not
# be left in a slot. tools/slot_erase.py snapshots each slot's task id now and, on ANY exit (a failed stage included),
# erases the idle slots whose task changed: a restored conversation of Mark's that this run never touched is kept.
# Store entries from earlier saves are untouched either way.
cd "$ROOT"
SLOTSNAP=$(mktemp); "$PY" "$ROOT/tools/slot_erase.py" snapshot "$SLOTSNAP" >> "$LOG" 2>&1
trap '"$PY" "$ROOT/tools/slot_erase.py" erase-changed "$SLOTSNAP" >> "$LOG" 2>&1; rm -f "$SLOTSNAP"' EXIT
echo "== $(date '+%F %T') nightly daydream" >> "$LOG"
"$PY" tools/daydream_harvest.py >> "$LOG" 2>&1 || { beat error "harvest failed"; notify "Daydream FAILED" "harvest stage; see $LOG"; exit 1; }
"$PY" tools/daydream_links.py >> "$LOG" 2>&1 || { beat error "links failed"; notify "Daydream FAILED" "links stage; see $LOG"; exit 1; }
OUT=$("$PY" tools/daydream_brief.py 2>> "$LOG" | tail -1)
ST=$(printf '%s' "$OUT" | "$PY" -c 'import json,sys; print(json.loads(sys.stdin.read()).get("status","error"))' 2>/dev/null || echo error)
if [ ! -s "$M/$D.md" ]; then beat error "no brief written: $OUT"; notify "Daydream FAILED" "no brief; see $LOG"; exit 1; fi
beat "$ST" "$OUT"
SUM=$(printf '%s' "$OUT" | "$PY" -c 'import json,sys; d=json.loads(sys.stdin.read()); print("%d picks, %d closed, %d likely closed, %d to check, %d BACKLOG edits" % (d.get("picks", 0), d.get("closed", 0), d.get("likely", 0), d.get("suggested", 0) - d.get("likely", 0), d.get("backlog_close", 0)))' 2>/dev/null || echo "see brief")
echo "Morning brief ($ST): $SUM -> data/dev_diaries/morning/$D.md" > "$ROOT/data/dev_diaries/.daydream_motd"
notify "Morning brief ready ($ST)" "$SUM\ndata/dev_diaries/morning/$D.md"
