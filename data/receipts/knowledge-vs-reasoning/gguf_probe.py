#!/usr/bin/env python3
"""Dependency-free GGUF header probe. Stdlib only — no numpy, no gguf-py.

Reads ONLY the header (KV metadata + tensor info records). Never touches the
tensor data section, so it is safe and fast against multi-GB files.

Used for Protocol_Measurement_Standard.md Phase-0 style gates:
  - packaging parity  : per-tensor type histogram + imatrix/file_type KVs
  - property-not-label: expert counts read from tensor shapes, not model cards
"""
import struct, sys, collections

# gguf value types
U8, I8, U16, I16, U32, I32, F32, BOOL, STR, ARR, U64, I64, F64 = range(13)
_FIX = {U8: ("<B", 1), I8: ("<b", 1), U16: ("<H", 2), I16: ("<h", 2),
        U32: ("<I", 4), I32: ("<i", 4), F32: ("<f", 4), BOOL: ("<?", 1),
        U64: ("<Q", 8), I64: ("<q", 8), F64: ("<d", 8)}

GGML = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1",
        8: "Q8_0", 9: "Q8_1", 10: "Q2_K", 11: "Q3_K", 12: "Q4_K", 13: "Q5_K",
        14: "Q6_K", 15: "Q8_K", 16: "IQ2_XXS", 17: "IQ2_XS", 18: "IQ3_XXS",
        19: "IQ1_S", 20: "IQ4_NL", 21: "IQ3_S", 22: "IQ2_S", 23: "IQ4_XS",
        24: "I8", 25: "I16", 26: "I32", 27: "I64", 28: "F64", 29: "IQ1_M",
        30: "BF16", 34: "TQ1_0", 35: "TQ2_0", 39: "MXFP4", 40: "NVFP4",
        45: "TQ3_1S", 46: "TQ4_1S"}


class R:
    def __init__(self, f):
        self.f = f

    def raw(self, n):
        b = self.f.read(n)
        if len(b) != n:
            raise EOFError("short read")
        return b

    def fix(self, t):
        fmt, n = _FIX[t]
        return struct.unpack(fmt, self.raw(n))[0]

    def string(self):
        return self.raw(self.fix(U64)).decode("utf-8", "replace")

    def value(self, t):
        if t == STR:
            return self.string()
        if t == ARR:
            et = self.fix(U32)
            n = self.fix(U64)
            if et == STR:                      # don't materialise huge token lists
                if n > 16:
                    for _ in range(n):
                        self.raw(self.fix(U64))
                    return f"<{n} strings>"
                return [self.string() for _ in range(n)]
            vals = [self.value(et) for _ in range(n)]
            return vals if n <= 16 else f"<{n} items, first={vals[0]}>"
        return self.fix(t)


INTEREST = ("imatrix", "file_type", "expert", "block_count", "quantization",
            "embedding_length", "architecture", "name")


def probe(path):
    print("=" * 74)
    print(path.rsplit("/", 1)[-1])
    print("=" * 74)
    with open(path, "rb") as f:
        r = R(f)
        if r.raw(4) != b"GGUF":
            print("  !! not a GGUF file"); return None
        ver = r.fix(U32)
        n_tensors = r.fix(U64)
        n_kv = r.fix(U64)
        print(f"  gguf v{ver}  tensors={n_tensors}  kv={n_kv}")

        kv = {}
        for _ in range(n_kv):
            k = r.string()
            kv[k] = r.value(r.fix(U32))

        print("  -- KV (filtered) --")
        for k in sorted(kv):
            if any(t in k.lower() for t in INTEREST):
                print(f"     {k:50s} = {str(kv[k])[:64]}")
        imat = [k for k in kv if "imatrix" in k.lower()]
        print(f"  -- imatrix KVs present: {len(imat)} {imat if imat else ''}")

        hist = collections.Counter()
        shapes = {}
        for _ in range(n_tensors):
            name = r.string()
            nd = r.fix(U32)
            dims = [r.fix(U64) for _ in range(nd)]
            tt = r.fix(U32)
            r.fix(U64)  # offset
            hist[GGML.get(tt, f"type_{tt}")] += 1
            if ("exps" in name) and len(shapes) < 3:
                shapes[name] = dims

        print("  -- tensor type histogram --")
        for name, n in sorted(hist.items(), key=lambda x: -x[1]):
            print(f"     {name:10s} {n:6d}")
        print("  -- sample expert tensors (shape) --")
        for name, dims in shapes.items():
            print(f"     {name:44s} {dims}")
        return hist, kv


if __name__ == "__main__":
    out = [probe(p) for p in sys.argv[1:]]
    if len(out) == 2 and all(out):
        a, b = out[0][0], out[1][0]
        print("\n" + "=" * 74)
        print("G-1 PACKAGING PARITY: per-tensor type recipe")
        print("=" * 74)
        for t in sorted(set(a) | set(b)):
            m = "" if (t in a) == (t in b) else "   <-- present in only one arm"
            print(f"  {t:10s} arm1={a.get(t,0):6d}  arm2={b.get(t,0):6d}{m}")
        print(f"\n  same type set: {set(a) == set(b)}")
