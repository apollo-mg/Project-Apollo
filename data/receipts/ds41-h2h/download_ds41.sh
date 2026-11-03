#!/usr/bin/env bash
# DeepSeek-V4.1-Flash-1017 head-to-head: download the two builds (Mark's OK, 2026-11-02), each pinned to the repo revision
# read on 11-02 and each file checked against its published LFS sha256. Matched at about 250 GB:
#   ISTA-DASLab GSQ-RCO IQ2_XXS: backbone 138.24 GB (5 shards) + the shared Engram tables, IQ4_NL, 110.60 GB (shard 6)
#   unsloth UD-IQ1_M:            250.40 GB (5 shards; shard 5 is 110.60 GB, apparently the same Engram at IQ4_NL)
# Two lanes in parallel, plain curl on resolve/<revision> URLs (public repos, no token). Resumable: rerun to continue; a
# file already verified is skipped. A hash mismatch renames the file to .bad and the run ends FAILED.
# Usage: download_ds41.sh DEST_DIR      (writes DEST_DIR/download.log; last line "ALL OK" or "FAILED <n>")
set -u
DEST=${1:?usage: download_ds41.sh DEST_DIR}
mkdir -p "$DEST/gsq" "$DEST/unsloth"
LOG="$DEST/download.log"
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

ISTA_REPO=ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF; ISTA_REV=65d53bc8be65123e255ff02f3ded958b6dbf54fd
UNS_REPO=unsloth/DeepSeek-V4.1-Flash-1017-GGUF;             UNS_REV=2688c0c3c2c3b052ec4f6d10a8417b0ef7ee4eba

# path size sha256 ("-" = not an LFS file: size check only)
GSQ_FILES="DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00001-of-00006.gguf 5780704 f356f198561f56df36f7ab92d7238a926646d76de992c34f15bcb939a5f529b9
DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00002-of-00006.gguf 39535781184 25af3785ccf925f54137e1ead4c481a8952315dc0b1af6519a99407f67bce8f3
DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00003-of-00006.gguf 39736712000 8168d0998fc494def2e1952d83c131425a108660aae9d29190f5a8670ab62b48
DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00004-of-00006.gguf 39036908384 9eb9b4de1968f150dfc207eb31c27be9cd9b5666a9a6246bde8a22b184b4bee0
DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00005-of-00006.gguf 19923784832 7e35f6b4e6fc46f6c4b152b593d84d683c5ece695ae6ad734f556198c041bec1
DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf 110595290816 3dac4c54893ad7aa89103c0028500eadc78e74112cef3a2930a97e67dc9fb4f3
chat_template.jinja 18509 -
tensor-allocation/DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS.rco-allocation.txt 34821 -"
UNS_FILES="UD-IQ1_M/DeepSeek-V4.1-Flash-1017-UD-IQ1_M-00001-of-00005.gguf 5780868 5197c309479c7be06e3612dc696d7f18e13e5942cfe52e70c3c586b7e585a5ac
UD-IQ1_M/DeepSeek-V4.1-Flash-1017-UD-IQ1_M-00002-of-00005.gguf 49707332128 fbfb546557a33f41332ffbed7f15fbed249b9f7796975d9db571c8cf3870f335
UD-IQ1_M/DeepSeek-V4.1-Flash-1017-UD-IQ1_M-00003-of-00005.gguf 49292777280 394b7a06e04d4b1b96b6028ec3d4dec49e4716900c26a493e8c2aa38a357ea1a
UD-IQ1_M/DeepSeek-V4.1-Flash-1017-UD-IQ1_M-00004-of-00005.gguf 40803165856 323a7f59a2938879eaac82b37c443c85151e518071ad44c79b1e4580c91d0ed7
UD-IQ1_M/DeepSeek-V4.1-Flash-1017-UD-IQ1_M-00005-of-00005.gguf 110595290592 771805301e695d72d268151dfc43043581ba904298574aa879d4349cbe67b020"

need=0
while read -r p s h; do f="$DEST/gsq/${p##*/}"; [ -e "$f.verified" ] || need=$((need + s - $(stat -c %s "$f" 2>/dev/null || echo 0))); done <<< "$GSQ_FILES"
while read -r p s h; do f="$DEST/unsloth/${p##*/}"; [ -e "$f.verified" ] || need=$((need + s - $(stat -c %s "$f" 2>/dev/null || echo 0))); done <<< "$UNS_FILES"
free=$(( $(df --output=avail -B1 "$DEST" | tail -1) ))
log "start: need $need bytes, free $free bytes"
if [ "$free" -lt $((need + 10000000000)) ]; then log "FAILED disk: need $need + 10 GB headroom, free $free"; exit 1; fi

lane() {   # lane SUBDIR REPO REV LIST
  local sub=$1 repo=$2 rev=$3 bad=0
  while read -r p s h; do
    local f="$DEST/$sub/${p##*/}"
    [ -e "$f.verified" ] && { log "$sub skip (verified) ${p##*/}"; continue; }
    log "$sub get ${p##*/} ($s bytes)"
    curl -fsSL --retry 30 --retry-delay 15 --retry-all-errors -C - -o "$f" "https://huggingface.co/$repo/resolve/$rev/$p" \
      || { log "$sub CURL-FAIL ${p##*/} rc=$?"; bad=$((bad + 1)); continue; }
    local got; got=$(stat -c %s "$f")
    [ "$got" = "$s" ] || { log "$sub SIZE-MISMATCH ${p##*/} got $got want $s"; mv "$f" "$f.bad"; bad=$((bad + 1)); continue; }
    if [ "$h" != "-" ]; then
      local sum; sum=$(sha256sum "$f" | cut -d' ' -f1)
      [ "$sum" = "$h" ] || { log "$sub SHA-MISMATCH ${p##*/} got $sum"; mv "$f" "$f.bad"; bad=$((bad + 1)); continue; }
    fi
    echo "$h" > "$f.verified"; log "$sub OK ${p##*/}"
  done <<< "$4"
  echo "$bad" > "$DEST/$sub.bad"
}
lane gsq "$ISTA_REPO" "$ISTA_REV" "$GSQ_FILES" &
lane unsloth "$UNS_REPO" "$UNS_REV" "$UNS_FILES" &
wait
# llama.cpp opens the Engram as shard 6 of the GSQ build (the publisher's layout)
ln -sfn DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf "$DEST/gsq/DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00006-of-00006.gguf"
n=$(( $(cat "$DEST/gsq.bad") + $(cat "$DEST/unsloth.bad") ))
[ "$n" = 0 ] && log "ALL OK" || log "FAILED $n"
