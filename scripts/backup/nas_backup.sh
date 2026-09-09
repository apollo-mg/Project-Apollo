#!/usr/bin/env bash
# Nightly backup of everything that isn't model-sized or regenerable.
#
# Rationale (2026-09-09): the Apollo repo tracks engines/ as submodules, so it stores
# POINTERS, not code. If an upstream fork is deleted and this disk fails, the code is gone.
# llama.cpp/ggml maintainers moved to Hugging Face (Feb 2026) and Hugging Face is being
# acquired by NVIDIA (closing H1 2027), so upstream availability is not a safe assumption.
#
# Backs up: receipts, notes, diaries, docs, skills, scripts, modules, tools, and a git
# bundle of every repo (full history in one file).
# Does NOT back up: models, venvs, build artifacts, archives -- all large and replaceable.
set -uo pipefail

SRC=/mnt/TG_2TB/Projects/Apollo
DEST=/mnt/HDD/apollo-backup
LOG=$SRC/run/nas_backup.log
mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "===== $(date -Iseconds) starting"

# refuse to run if the NAS isn't actually mounted -- otherwise we'd silently fill the local disk
if ! findmnt -M /mnt/HDD >/dev/null 2>&1; then
  echo "  ABORT: /mnt/HDD is not mounted (automount should have handled this)"
  exit 1
fi
mkdir -p "$DEST"/{tree,bundles}

echo "--- working tree (curated)"
rsync -a --delete --info=stats2 \
  --exclude='__pycache__/' --exclude='*.pyc' \
  "$SRC/data/receipts" "$SRC/notes" "$SRC/data/dev_diaries" \
  "$SRC/data/Apollo Docs" "$SRC/vault/skills" "$SRC/scripts" \
  "$SRC/modules" "$SRC/tools" "$SRC/profiles.yaml" \
  "$DEST/tree/" 2>&1 | tail -4

echo "--- git bundles (full history, one file per repo)"
bundle_one(){
  local repo="$1" name="$2"
  [ -d "$repo/.git" ] || return 0
  local head; head=$(git -C "$repo" rev-parse HEAD 2>/dev/null) || return 0
  local stamp="$DEST/bundles/$name.head"
  # only re-bundle when HEAD moved -- these are 100s of MB and change slowly
  if [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$head" ] && [ -f "$DEST/bundles/$name.bundle" ]; then
    echo "    $name: unchanged ($head)"; return 0
  fi
  echo -n "    $name: bundling $head ... "
  if git -C "$repo" bundle create "$DEST/bundles/$name.bundle.tmp" --all >/dev/null 2>&1; then
    mv "$DEST/bundles/$name.bundle.tmp" "$DEST/bundles/$name.bundle"
    echo "$head" > "$stamp"
    echo "ok ($(du -h "$DEST/bundles/$name.bundle" | cut -f1))"
  else
    rm -f "$DEST/bundles/$name.bundle.tmp"; echo "FAILED"
  fi
}
bundle_one "$SRC" apollo
for e in "$SRC"/engines/*/; do
  [ -d "$e/.git" ] && bundle_one "$e" "engine-$(basename "$e")"
done

echo "--- manifest"
{
  echo "backup taken $(date -Iseconds) from $(hostname)"
  echo "ROCm: $(hipconfig --version 2>/dev/null || echo n/a)"
  echo
  echo "repo HEADs at backup time:"
  git -C "$SRC" log -1 --format='  apollo %h %ad %s' --date=short 2>/dev/null
  for e in "$SRC"/engines/*/; do
    [ -d "$e/.git" ] && git -C "$e" log -1 --format="  $(basename "$e") %h %ad %s" --date=short 2>/dev/null
  done
  echo
  echo "restore: git clone <name>.bundle <dir>"
} > "$DEST/MANIFEST.txt"

echo "  total on NAS: $(du -sh "$DEST" 2>/dev/null | cut -f1)"
echo "===== $(date -Iseconds) done"
