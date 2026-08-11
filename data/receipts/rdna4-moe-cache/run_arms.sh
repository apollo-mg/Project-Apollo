#!/usr/bin/env bash
# P7 first: does --moe-cache change the output? Greedy, fixed seed, identical prompt.
# A cache is a residency optimisation; it must be byte-identical to cache-off.
set -u
SRC=/home/mark/moe-cache-test/src
OUT=/home/mark/moe-cache-test/arms
mkdir -p "$OUT"
M="/mnt/TG_2TB/AI/Models/Qwen 3.6/27B/MTP/Qwopus3.6-35B-A3B-v1.i1-Q4_K_M.gguf"
P="Explain what a mixture-of-experts router does, then list three tradeoffs."

run() {  # name, binary, extra flags
  local name="$1" bin="$2"; shift 2
  echo "########## $name"
  timeout 540 "$bin" -m "$M" -ngl 99 --cpu-moe -c 2048 --temp 0 --seed 1234 -n 96 -no-cnv \
      "$@" -p "$P" > "$OUT/$name.raw" 2>&1
  echo "  exit=$?"
  # strip loader noise + spinner to leave the generated text
  sed -e 's/[|\\/-]\{2,\}//g' "$OUT/$name.raw" \
    | grep -viE "^(llama_model_loader|load:|print_info|build |model |ftype |Loading model)" \
    | sed '/^[[:space:]]*$/d' > "$OUT/$name.txt"
  grep -iE "moe.?cache|expert cache|slab|budget" "$OUT/$name.raw" | head -4 | sed 's/^/  CACHE: /'
  grep -iE "eval time|tokens per second|^total time" "$OUT/$name.raw" | head -3 | sed 's/^/  PERF:  /'
}

run hip_off  "$SRC/build-hip/bin/llama-cli" --moe-cache off
run hip_4096 "$SRC/build-hip/bin/llama-cli" --moe-cache 4096

echo "########## P7: byte-identical?"
if diff -q "$OUT/hip_off.txt" "$OUT/hip_4096.txt" >/dev/null 2>&1; then
  echo "  IDENTICAL — P7 holds on HIP"
else
  echo "  DIFFERS — P7 FALSIFIED on HIP"
  diff "$OUT/hip_off.txt" "$OUT/hip_4096.txt" | head -20
fi
