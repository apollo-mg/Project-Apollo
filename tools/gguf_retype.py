#!/usr/bin/env python3
"""Rewrite ONE GGUF file (a shard is fine) converting only the tensors whose name matches REGEX from
BF16/F16/F32 to Q8_0. Everything else is copied byte for byte: the KV section verbatim, other tensors' data
verbatim, the same tensor order and alignment. Offsets are recomputed. Q8_0 is ggml's reference quantizer
(bit-exact with gguf-py's `quants.Q8_0`, which mirrors ggml-quants.c).

usage: gguf_retype.py IN.gguf OUT.gguf REGEX [--dry-run]
prints: converted tensor count, bytes before/after, and a sha256 of every NON-converted tensor's data in IN and OUT
(they must match) when --verify is given."""
import hashlib, re, struct, sys
import numpy as np

F32, F16, Q8_0, BF16 = 0, 1, 8, 30
SCALAR = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
CHUNK = 256 * 2**20


class R:
    def __init__(self, f): self.f = f
    def u(self, fmt):
        n = struct.calcsize("<" + fmt); return struct.unpack("<" + fmt, self.f.read(n))[0]
    def s(self):
        n = self.u("Q"); return self.f.read(n).decode("utf-8", "replace")
    def val(self, t):
        if t in SCALAR: return self.u(SCALAR[t])
        if t == 8: return self.s()
        if t == 9:
            et, n = self.u("I"), self.u("Q"); return [self.val(et) for _ in range(n)]
        raise ValueError(t)


def q8_0(x):
    """ggml quantize_row_q8_0_ref: d = amax/127 (stored fp16), q = roundf(x / d) (half away from zero)."""
    b = x.reshape(-1, 32).astype(np.float32)
    d = np.abs(b).max(axis=1, keepdims=True) / 127
    with np.errstate(divide="ignore"):
        idd = np.where(d == 0, 0, 1 / d)
    v = b * idd
    q = np.sign(v) * np.floor(np.abs(v) + 0.5)
    return np.concatenate([d.astype(np.float16).view(np.uint8), q.astype(np.int8).view(np.uint8)], axis=1).tobytes()


def to_f32(raw, t):
    if t == BF16:
        return (np.frombuffer(raw, np.uint16).astype(np.uint32) << 16).view(np.float32)
    if t == F16:
        return np.frombuffer(raw, np.float16).astype(np.float32)
    if t == F32:
        return np.frombuffer(raw, np.float32)
    raise ValueError(f"cannot convert type {t}")


def pad(n, a): return (n + a - 1) // a * a


def main():
    src, dst, rx = sys.argv[1], sys.argv[2], re.compile(sys.argv[3])
    dry, verify = "--dry-run" in sys.argv, "--verify" in sys.argv
    f = open(src, "rb"); r = R(f)
    assert f.read(4) == b"GGUF"
    ver, nt, nkv = r.u("I"), r.u("Q"), r.u("Q")
    kv_start = f.tell(); align = 32
    for _ in range(nkv):
        k = r.s(); t = r.u("I"); v = r.val(t)
        if k == "general.alignment": align = v
    kv_raw_end = f.tell()
    infos = []
    for _ in range(nt):
        name = r.s(); nd = r.u("I"); dims = [r.u("Q") for _ in range(nd)]; typ = r.u("I"); off = r.u("Q")
        infos.append([name, dims, typ, off])
    data0 = pad(f.tell(), align)
    fsize = f.seek(0, 2)
    order = sorted(range(nt), key=lambda i: infos[i][3])
    size = {}
    for j, i in enumerate(order):
        end = infos[order[j + 1]][3] if j + 1 < nt else fsize - data0
        size[i] = end - infos[i][3]                            # includes padding to alignment
    conv = [i for i in range(nt) if rx.search(infos[i][0])]
    for i in conv:
        assert infos[i][2] in (BF16, F16, F32), f"{infos[i][0]}: type {infos[i][2]} not float"
        assert infos[i][1][0] % 32 == 0, f"{infos[i][0]}: ne0 {infos[i][1][0]} not a multiple of 32"
    nel = lambda i: int(np.prod(infos[i][1]))
    new_len = {i: (nel(i) // 32 * 34 if i in conv else None) for i in range(nt)}
    old_bytes = sum(size[i] for i in conv); new_bytes = sum(pad(new_len[i], align) for i in conv)
    print(f"{src}: {nt} tensors, {len(conv)} to convert, {old_bytes/1e6:.1f} MB -> {new_bytes/1e6:.1f} MB")
    if dry:
        for i in conv[:6]: print("  ", infos[i][0], infos[i][1], infos[i][2])
        return
    # new offsets, same data order
    off, newoff = 0, {}
    for i in order:
        newoff[i] = off
        off += pad(new_len[i], align) if i in conv else size[i]
    with open(dst, "wb") as o:
        f.seek(0); o.write(f.read(kv_raw_end))                 # magic, version, counts, KV section: verbatim
        for i, (name, dims, typ, _) in enumerate(infos):
            nb = name.encode()
            o.write(struct.pack("<Q", len(nb)) + nb + struct.pack("<I", len(dims)) + b"".join(struct.pack("<Q", d) for d in dims))
            o.write(struct.pack("<IQ", Q8_0 if i in conv else typ, newoff[i]))
        o.write(b"\0" * (pad(o.tell(), align) - o.tell()))
        new_data0 = o.tell()
        for i in order:
            f.seek(data0 + infos[i][3])
            assert o.tell() == new_data0 + newoff[i]
            if i in conv:
                raw = f.read(nel(i) * {BF16: 2, F16: 2, F32: 4}[infos[i][2]])
                b = q8_0(to_f32(raw, infos[i][2])); o.write(b); o.write(b"\0" * (pad(len(b), align) - len(b)))
            else:
                left = size[i]
                while left:
                    buf = f.read(min(CHUNK, left)); o.write(buf); left -= len(buf)
    print(f"wrote {dst}")
    if verify:                                                 # every non-converted tensor must be byte-identical
        g = open(dst, "rb"); bad = 0
        for i in order:
            if i in conv: continue
            f.seek(data0 + infos[i][3]); g.seek(new_data0 + newoff[i])
            h1, h2, left = hashlib.sha256(), hashlib.sha256(), size[i]
            while left:
                n = min(CHUNK, left); h1.update(f.read(n)); h2.update(g.read(n)); left -= n
            bad += h1.digest() != h2.digest()
        print(f"verify: {nt - len(conv)} copied tensors, {bad} mismatches")
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
