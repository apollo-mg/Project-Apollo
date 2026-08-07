#!/usr/bin/env bash
# safekill — pattern-kill processes without ever killing yourself.
#
# WHY THIS EXISTS
# `pkill -f <pattern>` / `pgrep -f <pattern>` match against full command lines, INCLUDING the
# command line of the shell that is doing the searching. Over ssh that shell is
# `bash -c '... pgrep -f "llama-server" ...'`, which contains the pattern, so the search matches
# itself and the kill takes down the session (exit 255).
#
# This has now happened twice in this project:
#   2026-08-06  pkill -f "llama-server.*GLM-4.7-Flash-Q6_K.gguf"  -> killed the ssh shell
#   2026-08-07  pgrep -f "pfetch.sh"                              -> killed the ssh shell mid-transfer
#
# A written rule did not prevent the second one. So this is the rule as a tool: the failure is
# structurally impossible here because self and every ancestor are excluded before anything is
# signalled. Same discipline the measurement harnesses use -- preflight() aborts rather than warns,
# assert_gating() exits rather than prints.
#
# USAGE
#   safekill.sh <pattern>                 # DRY RUN (default) — prints what it would kill
#   safekill.sh <pattern> --force         # actually signal them
#   safekill.sh <pattern> --force -9      # SIGKILL instead of SIGTERM
#   safekill.sh --exact <name> --force    # match process NAME exactly (pgrep -x), not cmdline
#
# Exit: 0 if it ran (even with no matches), 1 on misuse, 2 if the guard tripped.
set -u

PATTERN=""; FORCE=0; SIG="-TERM"; EXACT=0; MAXKILL=25
while [ $# -gt 0 ]; do
  case "$1" in
    --force) FORCE=1 ;;
    --exact) EXACT=1 ;;
    -9|-KILL) SIG="-KILL" ;;
    -*) echo "unknown flag: $1" >&2; exit 1 ;;
    *) [ -z "$PATTERN" ] && PATTERN="$1" || { echo "one pattern only" >&2; exit 1; } ;;
  esac
  shift
done
[ -z "$PATTERN" ] && { echo "usage: safekill.sh <pattern> [--exact] [--force] [-9]" >&2; exit 1; }

# ---- build the protected set: self + every ancestor up to init -------------------------------
# This is the whole point. Over ssh the ancestor chain is
#   sshd -> bash -c '<command containing PATTERN>' -> safekill.sh
# so without this, a cmdline match kills the session.
PROTECTED=" $$ "
p=$$
while :; do
  ppid=$(awk '{print $4}' "/proc/$p/stat" 2>/dev/null) || break
  [ -z "$ppid" ] || [ "$ppid" -le 1 ] && break
  PROTECTED="$PROTECTED $ppid "
  p=$ppid
done
# also protect the session leader and anything sshd
SIDS=$(ps -o sid= -p $$ 2>/dev/null | tr -d ' ')
[ -n "$SIDS" ] && PROTECTED="$PROTECTED $SIDS "

protected() { case "$PROTECTED" in *" $1 "*) return 0 ;; esac; return 1; }

# ---- find candidates -------------------------------------------------------------------------
if [ "$EXACT" = 1 ]; then
  CAND=$(pgrep -x "$PATTERN" 2>/dev/null || true)
else
  CAND=$(pgrep -f -- "$PATTERN" 2>/dev/null || true)
fi

TARGETS=""; SKIPPED=""
for pid in $CAND; do
  [ -d "/proc/$pid" ] || continue
  if protected "$pid"; then SKIPPED="$SKIPPED $pid"; continue; fi
  # a process whose cmdline contains this script's own name is a searcher, not a target
  cl=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null)
  case "$cl" in *safekill*) SKIPPED="$SKIPPED $pid"; continue ;; esac
  TARGETS="$TARGETS $pid"
done

n=$(echo $TARGETS | wc -w)
echo "safekill: pattern='$PATTERN' exact=$EXACT  matches=$n  protected/skipped=$(echo $SKIPPED | wc -w)"
[ -n "$SKIPPED" ] && echo "  skipped (self/ancestor/searcher):$SKIPPED"
[ "$n" = 0 ] && { echo "  nothing to do"; exit 0; }

for pid in $TARGETS; do
  cl=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | cut -c1-110)
  echo "  $pid  $cl"
done

if [ "$n" -gt "$MAXKILL" ] && [ "$FORCE" = 1 ]; then
  echo "GUARD: $n matches exceeds MAXKILL=$MAXKILL — refusing. Narrow the pattern." >&2
  exit 2
fi

if [ "$FORCE" != 1 ]; then
  echo "  (dry run — re-run with --force to signal them)"
  exit 0
fi

for pid in $TARGETS; do kill "$SIG" "$pid" 2>/dev/null; done
sleep 2
LEFT=""
for pid in $TARGETS; do [ -d "/proc/$pid" ] && LEFT="$LEFT $pid"; done
if [ -n "$LEFT" ]; then echo "  still alive after $SIG:$LEFT"; else echo "  all signalled processes gone"; fi
echo "safekill: done (session intact)"
