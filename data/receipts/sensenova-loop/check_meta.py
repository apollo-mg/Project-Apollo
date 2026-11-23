#!/usr/bin/env python3
"""PREREG_SENSENOVA_LOOP Deviation 1 (G1): read the GGUF header and print 'ARCH LOOP_COUNT BLOCK_COUNT'.
Usage: check_meta.py FILE.gguf"""
import struct, sys
f = open(sys.argv[1], "rb"); assert f.read(4) == b"GGUF"
ver, nt, nkv = struct.unpack("<IQQ", f.read(20))
def rs(): n, = struct.unpack("<Q", f.read(8)); return f.read(n).decode("utf-8", "replace")
SZ = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
def rv(t):
    if t == 8: return rs()
    if t == 9:
        et, n = struct.unpack("<IQ", f.read(12)); return [rv(et) for _ in range(n)]
    fmt = "<" + SZ[t]; return struct.unpack(fmt, f.read(struct.calcsize(fmt)))[0]
kv = {}
for _ in range(nkv):
    k = rs(); t, = struct.unpack("<I", f.read(4)); kv[k] = rv(t) if not k.startswith("tokenizer.ggml.") else (rv(t) and None)
a = kv["general.architecture"]
print(a, kv.get(f"{a}.loop.count"), kv.get(f"{a}.block_count"))
