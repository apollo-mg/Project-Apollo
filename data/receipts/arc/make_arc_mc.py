#!/usr/bin/env python3
"""Convert ARC-Challenge (test split) to llama.cpp's --multiple-choice binary format.

Format reverse-engineered from tools/perplexity/perplexity.cpp (buun fork, 2026-07-20):

    uint32              n_task
    uint32[n_task]      byte offset of each task from stream start
    per task:
      string            question          (uint32 byte-length + raw utf-8, no NUL)
      mc1: uint32 n, n x string, n x int32 labels   (label 1 = correct)
      mc2: uint32 n, ...                            (declared "not handled yet" -> we write n=0)

Scoring in llama.cpp: each answer is tokenized as `question + " " + answer`, the sequence
logprob is summed, and argmax is taken; correct if labels[argmax] == 1. NOTE this is the
UNNORMALIZED variant — equivalent to lm-eval's `acc`, not `acc_norm`. Published ARC numbers
are frequently acc_norm, so absolute cross-comparison is unsafe. The matched
DavidAU-vs-stock delta measured here is the trustworthy quantity.
"""
import struct, sys
from datasets import load_dataset

OUT = sys.argv[1] if len(sys.argv) > 1 else "arc_challenge_test.mc.bin"

ds = load_dataset("allenai/ai2_arc", "ARC-Challenge", split="test")
print(f"loaded {len(ds)} ARC-Challenge test items")

def enc_str(s: str) -> bytes:
    b = s.encode("utf-8")
    return struct.pack("<I", len(b)) + b

tasks, skipped = [], 0
for row in ds:
    q = (row["question"] or "").strip()
    choices = row["choices"]
    texts = [t.strip() for t in choices["text"]]
    keys = list(choices["label"])
    ans = row["answerKey"]

    # A handful of ARC rows use numeric keys ("1".."4") instead of "A".."D"
    if ans not in keys or not q or not texts or any(not t for t in texts):
        skipped += 1
        continue
    labels = [1 if k == ans else 0 for k in keys]
    if sum(labels) != 1:
        skipped += 1
        continue

    blob = enc_str(q)
    blob += struct.pack("<I", len(texts))
    for t in texts:
        blob += enc_str(t)
    blob += struct.pack("<" + "i" * len(labels), *labels)
    blob += struct.pack("<I", 0)          # mc2: zero answers
    tasks.append(blob)

print(f"encoded {len(tasks)} tasks, skipped {skipped}")

n = len(tasks)
header_size = 4 + 4 * n
offsets, pos = [], header_size
for t in tasks:
    offsets.append(pos)
    pos += len(t)

with open(OUT, "wb") as f:
    f.write(struct.pack("<I", n))
    f.write(struct.pack("<" + "I" * n, *offsets))
    for t in tasks:
        f.write(t)

print(f"wrote {OUT} ({pos} bytes)")

# --- self-verify: read it back exactly the way llama.cpp does -------------------
with open(OUT, "rb") as f:
    data = f.read()
import io
s = io.BytesIO(data)
n_r = struct.unpack("<I", s.read(4))[0]
pos_r = struct.unpack("<" + "I" * n_r, s.read(4 * n_r))
assert n_r == n, "task count mismatch"

def rd_str(st):
    ln = struct.unpack("<I", st.read(4))[0]
    return st.read(ln).decode("utf-8")

ok = 0
for i in (0, 1, n // 2, n - 1):
    s.seek(pos_r[i])
    q = rd_str(s)
    na = struct.unpack("<I", s.read(4))[0]
    answers = [rd_str(s) for _ in range(na)]
    labs = struct.unpack("<" + "i" * na, s.read(4 * na))
    n2 = struct.unpack("<I", s.read(4))[0]
    assert n2 == 0 and sum(labs) == 1
    ok += 1
    if i == 0:
        print(f"  verify task0: q={q[:60]!r} n_answers={na} correct={answers[labs.index(1)][:40]!r}")
print(f"self-verify OK on {ok} sampled tasks (offsets, strings, labels all parse)")
