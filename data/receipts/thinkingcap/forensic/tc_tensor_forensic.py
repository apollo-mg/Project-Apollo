#!/usr/bin/env python3
"""Tensor-level forensic: ThinkingCap Q8_0-MTP vs standalone head vs stock Q8_0.
Prints per-tensor name/type/size/md5 comparisons only — no tensor data to stdout."""
import hashlib
import os
import sys

sys.path.insert(0, os.path.expanduser("~/llama_stock/gguf-py"))
from gguf import GGUFReader  # noqa: E402

TC_MAIN = os.path.expanduser("~/AI/Models/Qwen 3.6/27B-ThinkingCap/ThinkingCap-Qwen3.6-27B-Q8_0-MTP.gguf")
TC_HEAD = os.path.expanduser("~/AI/Models/Qwen 3.6/27B-ThinkingCap/mtp-ThinkingCap-head-Q8_0.gguf")
STOCK = os.path.expanduser("~/AI/Models/Qwen 3.6/27B/Qwen3.6-27B-Q8_0.gguf")


def index(path):
    r = GGUFReader(path)
    out = {}
    for t in r.tensors:
        data = t.data
        h = hashlib.md5()
        # hash in 64MB chunks off the mmap to keep RSS flat
        mv = memoryview(data.reshape(-1).view("uint8"))
        step = 64 * 1024 * 1024
        for i in range(0, len(mv), step):
            h.update(mv[i:i + step])
        out[t.name] = (str(t.tensor_type).split(".")[-1], int(mv.nbytes), h.hexdigest())
    return out


def is_mtp(name):
    n = name.lower()
    return any(k in n for k in ("mtp", "nextn", "eh_proj", "shared_head", "embed_tokens_mtp"))


print("== indexing (this reads ~61GB, be patient) ==", flush=True)
main = index(TC_MAIN)
print(f"TC_MAIN: {len(main)} tensors", flush=True)
head = index(TC_HEAD)
print(f"TC_HEAD: {len(head)} tensors", flush=True)
stock = index(STOCK)
print(f"STOCK:   {len(stock)} tensors", flush=True)

print("\n== TC_HEAD tensor listing ==")
for n, (ty, sz, md) in sorted(head.items()):
    print(f"  {n:60s} {ty:8s} {sz:>14,d} {md}")

print("\n== MTP-pattern tensors in TC_MAIN ==")
mtp_main = {n: v for n, v in main.items() if is_mtp(n)}
for n, (ty, sz, md) in sorted(mtp_main.items()):
    print(f"  {n:60s} {ty:8s} {sz:>14,d} {md}")
if not mtp_main:
    print("  (none matched pattern — dumping names NOT present in STOCK instead)")
    for n in sorted(set(main) - set(stock)):
        ty, sz, md = main[n]
        print(f"  {n:60s} {ty:8s} {sz:>14,d} {md}")

print("\n== CHECK 1: TC_MAIN embedded MTP vs TC_HEAD standalone ==")
head_hashes = {v[2]: n for n, v in head.items()}
main_only = set(main) - set(stock)
match = same_name = 0
for n in sorted(main_only):
    ty, sz, md = main[n]
    if md in head_hashes:
        match += 1
        tag = f"BYTE-MATCH -> head:{head_hashes[md]}"
    elif n in head:
        same_name += 1
        tag = f"NAME-MATCH but hash differs (head: {head[n][2]})"
    else:
        tag = "NO COUNTERPART in head file"
    print(f"  {n:60s} {tag}")
print(f"  summary: {len(main_only)} main-only tensors, {match} byte-match head, {same_name} differ")
# also reverse: head tensors with no byte-match in main
rev = [n for n, v in head.items() if v[2] not in {x[2] for x in main.values()}]
print(f"  head tensors with NO byte-match in main: {len(rev)}")
for n in sorted(rev):
    print(f"    {n}  {head[n][0]}  {head[n][1]:,d}  {head[n][2]}")

print("\n== CHECK 2: TC body vs STOCK Q8_0 (common tensor names) ==")
common = sorted(set(main) & set(stock))
ident = diff = typediff = 0
diffs = []
for n in common:
    tm, sm, hm = main[n]
    ts, ss, hs = stock[n]
    if tm != ts or sm != ss:
        typediff += 1
        diffs.append((n, f"TYPE/SIZE differ: TC {tm}/{sm:,d} vs STOCK {ts}/{ss:,d}"))
    elif hm == hs:
        ident += 1
    else:
        diff += 1
        diffs.append((n, "bytes differ"))
print(f"  common tensors: {len(common)}  byte-identical: {ident}  differ: {diff}  type/size-mismatch: {typediff}")
print("  --- differing tensors (first 400) ---")
for n, why in diffs[:400]:
    print(f"  {n:60s} {why}")
missing = sorted(set(stock) - set(main))
print(f"  stock-only tensors (absent in TC): {len(missing)}")
for n in missing[:50]:
    print(f"    {n}")
print("\nDONE_FORENSIC")
