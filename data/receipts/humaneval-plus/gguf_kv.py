#!/usr/bin/env python3
"""Dump a GGUF's header KV pairs (no tensor data read). Optionally filter by substring.
Usage: gguf_kv.py <model.gguf> [substr ...]
Rebuild of the reader lost in the 2026-07-25 scratchpad wipe; used here to answer
'does this GGUF carry MTP / nextn layers?' without loading 30GB onto a GPU."""
import struct, sys

U8,I8,U16,I16,U32,I32,F32,BOOL,STR,ARR,U64,I64,F64 = range(13)
FIXED = {U8:1,I8:1,U16:2,I16:2,U32:4,I32:4,F32:4,BOOL:1,U64:8,I64:8,F64:8}
FMT   = {U8:"<B",I8:"<b",U16:"<H",I16:"<h",U32:"<I",I32:"<i",F32:"<f",
         BOOL:"<?",U64:"<Q",I64:"<q",F64:"<d"}

class R:
    def __init__(s, f): s.f = f
    def raw(s, n): return s.f.read(n)
    def u32(s): return struct.unpack("<I", s.raw(4))[0]
    def u64(s): return struct.unpack("<Q", s.raw(8))[0]
    def val(s, t):
        if t in FIXED: return struct.unpack(FMT[t], s.raw(FIXED[t]))[0]
        if t == STR:   return s.raw(s.u64()).decode("utf-8", "replace")
        if t == ARR:
            et = s.u32(); n = s.u64()
            vals = [s.val(et) for _ in range(n)]
            return f"<array[{n}] of type {et}>" if n > 8 else vals
        raise ValueError(f"bad type {t}")

def main():
    path  = sys.argv[1]
    terms = [t.lower() for t in sys.argv[2:]]
    with open(path, "rb") as f:
        r = R(f)
        if r.raw(4) != b"GGUF": print("NOT A GGUF"); return 1
        ver = r.u32(); ntensor = r.u64(); nkv = r.u64()
        print(f"=== {path.split('/')[-1]} ===")
        print(f"  gguf v{ver}  tensors={ntensor}  kv_pairs={nkv}")
        hits = 0
        for _ in range(nkv):
            k = r.raw(r.u64()).decode("utf-8", "replace")
            v = r.val(r.u32())
            if not terms or any(t in k.lower() for t in terms):
                sv = str(v)
                print(f"  {k} = {sv[:160]}")
                hits += 1
        if terms and not hits:
            print(f"  (no KV key matched {terms})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
