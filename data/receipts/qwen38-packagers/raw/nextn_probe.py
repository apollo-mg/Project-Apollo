#!/usr/bin/env python3
"""What type is the MTP draft head, per packager and per quant?

Motivated by the split between this fleet's MTP result (2.05x faster on RDNA4,
1.52x on Pascal, both on unsloth files) and the "MTP makes Qwen 3.8 slower"
reports from two other people. Speculative decoding pays only if the draft is
accepted, and the draft head is a handful of tensors that a packager can quantise
independently of the model. If packagers disagree about its precision, both
observations can be correct about different files.
"""
import collections, struct, sys, urllib.parse
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/modules")
import gguf_librarian as g

TARGETS = [
    ("bartowski", "Qwen3.8-27B-Q6_K.gguf"),
    ("bartowski", "Qwen3.8-27B-Q4_K_M.gguf"),
    ("bartowski", "Qwen3.8-27B-IQ3_XXS.gguf"),
    ("bartowski", "Qwen3.8-27B-Q8_0.gguf"),
    ("unsloth",   "Qwen3.8-27B-Q6_K.gguf"),
    ("unsloth",   "Qwen3.8-27B-UD-Q6_K_XL.gguf"),
    ("unsloth",   "Qwen3.8-27B-UD-IQ3_XXS.gguf"),   # the file this fleet benchmarked
    ("unsloth",   "Qwen3.8-27B-UD-IQ2_M.gguf"),
]

def tensors(url):
    f = g._HTTPFile(url)
    if f.read(4) != b"GGUF":
        raise ValueError("not a GGUF")
    struct.unpack("<I", f.read(4))
    n_t, n_kv = struct.unpack("<QQ", f.read(16))
    for _ in range(n_kv):
        f.read(struct.unpack("<Q", f.read(8))[0])
        g._val(f, struct.unpack("<I", f.read(4))[0])
    out = []
    for _ in range(n_t):
        nm = f.read(struct.unpack("<Q", f.read(8))[0]).decode("utf-8", "replace")
        nd = struct.unpack("<I", f.read(4))[0]
        ne = [struct.unpack("<Q", f.read(8))[0] for _ in range(nd)]
        ty = struct.unpack("<I", f.read(4))[0]
        struct.unpack("<Q", f.read(8))
        out.append((nm, ne, g.TRAITS.get(ty, (f"type{ty}", 0, 0))[0]))
    return out, f.size, f.fetched

print(f"{'packager':10s} {'file':34s} {'size':>9}  {'MTP-layer types':30s} {'body types'}")
for owner, fn in TARGETS:
    url = f"https://huggingface.co/{owner}/Qwen3.8-27B-GGUF/resolve/main/" + urllib.parse.quote(fn)
    try:
        ts, size, got = tensors(url)
    except Exception as e:
        print(f"{owner:10s} {fn:34s}  ERROR {type(e).__name__}: {e}")
        continue
    # the MTP head: llama.cpp names it blk.<n>.nextn.*, and the whole block that
    # carries it is the draft layer
    nextn_blocks = {nm.split(".")[1] for nm, _, _ in ts if ".nextn." in nm}
    mtp = collections.Counter(t for nm, _, t in ts
                              if nm.split(".")[1:2] and nm.split(".")[1] in nextn_blocks
                              and nm.startswith("blk.") and t != "F32")
    body = collections.Counter(t for nm, _, t in ts
                               if nm.startswith("blk.") and nm.split(".")[1] not in nextn_blocks
                               and t != "F32")
    fmt = lambda c: " + ".join(f"{t}x{n}" for t, n in sorted(c.items(), key=lambda kv: -kv[1]))
    print(f"{owner:10s} {fn:34s} {size/2**30:8.2f}G  {fmt(mtp) or '(no MTP layer)':30s} {fmt(body)}")
