#!/bin/bash
# Stages test 11's two files on .194 and verifies them there. Launch detached FROM A FOREGROUND CALL.
set -u
cd /mnt/TG_2TB/Projects/Apollo || exit 1
E=data/receipts/exl3-campaign
LOG=$E/usable/stage.log
N=10.0.0.194
SRC_EXL3=/mnt/TG_2TB/AI/Models/exl3/Qwen3.8-27B-exl3-3.00bpw
SRC_GGUF="/mnt/TG_2TB/AI/Models/Qwen 3.8/27B/Qwen3.8-27B-UD-IQ3_XXS.gguf"
mkdir -p "$E/usable"
log () { echo "$(date '+%F %T') $*" >> "$LOG"; }
die () { log "ABORT: $*"; exit 1; }
log "staging test 11 files on $N"

[ -d "$SRC_EXL3" ] || die "missing $SRC_EXL3"
[ -f "$SRC_GGUF" ] || die "missing $SRC_GGUF"

# 1. the GGUF against unsloth's published sha256 AT THE REVISION WE HOLD.
# unsloth re-cut UD-IQ3_XXS on 2026-08-19: rev f9758630 is 11,913,559,104 B / 0a6129dc...; every later
# revision is 10,934,860,704 B / c0b7c303.... Ours is f9758630, and it is the file test 10 measured.
EXPECTED_GGUF_SHA=0a6129dcbbbe72f423dc67e0e3bbfbbdf3e923981a3637687ebb96a46c59d6be
GGUF_REV=f9758630
LOCAL=$(sha256sum "$SRC_GGUF" | cut -d' ' -f1)
[ "$LOCAL" = "$EXPECTED_GGUF_SHA" ] || die "GGUF sha256 $LOCAL != $EXPECTED_GGUF_SHA (unsloth rev $GGUF_REV)"
log "GGUF verified against unsloth rev $GGUF_REV ($EXPECTED_GGUF_SHA)"
printf '{"file":"%s","unsloth_revision":"%s","sha256":"%s"}\n' "$(basename "$SRC_GGUF")" "$GGUF_REV" "$LOCAL" \
  > "$E/usable/published_gguf.json"

# 2. manifest of the EXL3 snapshot from the hf_fetch-verified copy
( cd "$SRC_EXL3" && find . -type f ! -name '.*' -printf '%P\n' | sort | xargs -d '\n' -P 8 -n 1 sha256sum ) \
  > "$E/usable/manifest_exl3_300.txt" || die "manifest failed"
log "manifest: $(wc -l < "$E/usable/manifest_exl3_300.txt") files; template sha $(sha256sum "$SRC_EXL3/chat_template.jinja" | cut -c1-16)"

# 3. copy, then verify on the far side
FREE=$(timeout 60 ssh -o BatchMode=yes "$N" "df -BG --output=avail ~ | tail -1 | tr -dc 0-9")
[ "${FREE:-0}" -ge 40 ] || die "only ${FREE:-?} GB free on $N"
timeout 3600 rsync -a --partial "$SRC_EXL3" "$N:AI/Models/exl3/" || die "EXL3 copy failed"
timeout 3600 rsync -a --partial "$SRC_GGUF" "$N:AI/Models/qwen27b/" || die "GGUF copy failed"
scp -q -o BatchMode=yes "$E/usable/manifest_exl3_300.txt" "$N:test11_manifest_exl3.txt" || die "manifest copy failed"
log "copied; verifying on $N"
R=$(timeout 1800 ssh -o BatchMode=yes "$N" '
  cd ~/AI/Models/exl3/Qwen3.8-27B-exl3-3.00bpw && sha256sum -c ~/test11_manifest_exl3.txt --quiet && echo EXL3-OK
  sha256sum ~/AI/Models/qwen27b/Qwen3.8-27B-UD-IQ3_XXS.gguf | cut -d" " -f1')
log "far-side verify: $R"
echo "$R" | grep -q EXL3-OK || die "EXL3 manifest check failed on $N"
[ "$(echo "$R" | tail -1)" = "$EXPECTED_GGUF_SHA" ] || die "GGUF sha on $N does not match unsloth rev $GGUF_REV"
log "=== STAGING COMPLETE ==="
