#!/usr/bin/env python3
"""Rewrite SenseNova-Loop-9B's GGUF for another loop count, weights untouched (for llama.cpp PR 32588 at 4bc61eed7).
The loader unrolls the loop: n_layer = 4 + 24*count + 4 logical layers, the tail stored under its logical index and the
MTP layer at index n_layer. For count c this sets block_count = n_layer + 1, loop.count = c, rebuilds the per-layer
attention list (3 linear : 1 full, which 24-layer passes preserve; MTP full), renames blk.52-55 -> the new tail indices
and blk.56 -> the new MTP index (same-length names), and copies the data section verbatim (offsets are relative to it).
Self-test: count 2 must reproduce the original file byte for byte.
Usage: rewrite_loops.py IN.gguf COUNT OUT.gguf|-   ('-' = hash only, nothing written)"""
import hashlib, re, struct, sys
SRC, C, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
ARCH = "sensenova_loop"; START, LOOPW = 4, 24
f = open(SRC, "rb"); hdr = bytearray()
def rd(n): b = f.read(n); hdr.extend(b); return b
assert rd(4) == b"GGUF"
ver, nt, nkv = struct.unpack("<IQQ", rd(20))
SZ = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
def rstr(): n, = struct.unpack("<Q", rd(8)); return rd(n).decode("utf-8")
def skipv(t):
    if t == 8: rstr(); return
    if t == 9:
        et, n = struct.unpack("<IQ", rd(12))
        if et in SZ: rd(SZ[et] * n)
        else:
            for _ in range(n): skipv(et)
        return
    rd(SZ[t])
enc_str = lambda s: struct.pack("<Q", len(s.encode())) + s.encode()
n_layer = START + LOOPW * C + 4
out = bytearray(hdr[:4]) + struct.pack("<IQQ", ver, nt, nkv)
for _ in range(nkv):
    a = len(hdr); k = rstr(); t, = struct.unpack("<I", rd(4)); skipv(t); raw = bytes(hdr[a:])
    if k == f"{ARCH}.block_count":
        assert t == 4; raw = enc_str(k) + struct.pack("<II", 4, n_layer + 1)
    elif k == f"{ARCH}.loop.count":
        assert t == 4; raw = enc_str(k) + struct.pack("<II", 4, C)
    elif k == f"{ARCH}.attention.recurrent_layers":
        vals = [0 if (il % 4 == 3) else 1 for il in range(n_layer)] + [0]       # MTP layer: full attention
        raw = enc_str(k) + struct.pack("<IIQ", 9, 7, len(vals)) + bytes(vals)
    out += raw
ren = {52 + j: START + LOOPW * C + j for j in range(4)}; ren[56] = n_layer
for _ in range(nt):
    name = rstr(); nd, = struct.unpack("<I", rd(4)); rest = rd(8 * nd + 12)
    m = re.match(r"blk\.(\d+)\.(.*)", name)
    if m and int(m.group(1)) in ren:
        new = f"blk.{ren[int(m.group(1))]}.{m.group(2)}"; assert len(new) == len(name), (name, new); name = new
    out += enc_str(name) + struct.pack("<I", nd) + rest
align = 32
data_start_in = (len(hdr) + align - 1) // align * align
out += b"\0" * ((-len(out)) % align)
f.seek(data_start_in)
h = hashlib.sha256(); w = open(OUT, "wb") if OUT != "-" else None
def emit(b):
    h.update(b)
    if w: w.write(b)
emit(bytes(out))
while True:
    b = f.read(1 << 24)
    if not b: break
    emit(b)
if w: w.close()
print(f"count {C}: n_layer {n_layer}, block_count {n_layer + 1}, header {len(out)} B (in {data_start_in}), sha256 {h.hexdigest()}")
