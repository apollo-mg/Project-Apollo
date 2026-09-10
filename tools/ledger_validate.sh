#!/usr/bin/env bash
# Thin wrapper so both observers can shell out to one check. Logic lives in ledger_validate.py
# (the rules need character-frequency counting, which bash does badly).
set -u
ROOT=/mnt/TG_2TB/Projects/Apollo
exec $ROOT/venv_cachyos/bin/python3 $ROOT/tools/ledger_validate.py "$@"
