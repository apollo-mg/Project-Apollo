#!/usr/bin/env python3
"""Dump GGUF tensor types over HTTP range requests -- no full download.

The tensor table sits at the head of a GGUF, so a few MiB of each shard is
enough to enumerate every tensor's ggml type. Used to answer "which types does
this dynamic quant put on the expert tensors" without pulling 60+ GiB.
"""
import collections, struct, sys, urllib.request

GT = {0:"F32",1:"F16",2:"Q4_0",3:"Q4_1",6:"Q5_0",7:"Q5_1",8:"Q8_0",9:"Q8_1",
      10:"Q2_K",11:"Q3_K",12:"Q4_K",13:"Q5_K",14:"Q6_K",15:"Q8_K",
      16:"IQ2_XXS",17:"IQ2_XS",18:"IQ3_XXS",19:"IQ1_S",20:"IQ4_NL",21:"IQ3_S",
      22:"IQ2_S",23:"IQ4_XS",24:"I8",25:"I16",26:"I32",27:"I64",28:"F64",
      29:"IQ1_M",30:"BF16",31:"TQ1_0",32:"TQ2_0",39:"MXFP4"}


class Ranged:
    """Lazily pulls byte ranges so we never fetch more than the header needs."""
    def __init__(self, url, chunk=4 << 20):
        self.url, self.chunk, self.buf, self.pos = url, chunk, b"", 0

    def _need(self, upto):
        while len(self.buf) < upto:
            lo, hi = len(self.buf), len(self.buf) + self.chunk - 1
            req = urllib.request.Request(self.url, headers={"Range": f"bytes={lo}-{hi}"})
            with urllib.request.urlopen(req, timeout=90) as r:
                blk = r.read()
            if not blk:
                raise EOFError("range request returned nothing")
            self.buf += blk

    def read(self, n):
        self._need(self.pos + n)
        out = self.buf[self.pos:self.pos + n]
        self.pos += n
        return out


def parse(url):
    f = Ranged(url)
    assert f.read(4) == b"GGUF", "not a GGUF"
    ver, = struct.unpack("<I", f.read(4))
    nt, = struct.unpack("<Q", f.read(8))
    nkv, = struct.unpack("<Q", f.read(8))

    def rs():
        n, = struct.unpack("<Q", f.read(8))
        return f.read(n).decode("utf-8", "replace")

    S = {0:"<b",1:"<B",2:"<h",3:"<H",4:"<i",5:"<I",6:"<f",7:"<?",10:"<q",11:"<Q",12:"<d"}

    def rv(t):
        if t == 8:
            return rs()
        if t == 9:
            et, = struct.unpack("<I", f.read(4))
            ln, = struct.unpack("<Q", f.read(8))
            return [rv(et) for _ in range(ln)]
        fmt = S[t]
        return struct.unpack(fmt, f.read(struct.calcsize(fmt)))[0]

    meta = {}
    for _ in range(nkv):
        k = rs()
        t, = struct.unpack("<I", f.read(4))
        v = rv(t)
        if any(s in k for s in ("architecture", "expert", "block_count", "split")):
            meta[k] = v

    exps, other, byname = collections.Counter(), collections.Counter(), {}
    for _ in range(nt):
        name = rs()
        nd, = struct.unpack("<I", f.read(4))
        for _ in range(nd):
            struct.unpack("<Q", f.read(8))
        ty, = struct.unpack("<I", f.read(4))
        struct.unpack("<Q", f.read(8))
        t = GT.get(ty, f"type{ty}")
        if "_exps" in name:
            exps[t] += 1
            base = name.split(".")[-2] if "." in name else name
            byname[base] = byname.get(base, collections.Counter())
            byname[base][t] += 1
        else:
            other[t] += 1
    return ver, nt, meta, exps, other, byname


if __name__ == "__main__":
    tot_e, tot_o, tot_by = collections.Counter(), collections.Counter(), {}
    for url in sys.argv[1:]:
        try:
            ver, nt, meta, e, o, by = parse(url)
        except Exception as ex:
            print(f"  {url.rsplit('/',1)[-1]}: FAILED {type(ex).__name__}: {ex}")
            continue
        print(f"  {url.rsplit('/',1)[-1]}: {nt} tensors  experts={dict(e)}")
        if meta:
            print(f"     meta: {meta}")
        tot_e.update(e); tot_o.update(o)
        for k, v in by.items():
            tot_by.setdefault(k, collections.Counter()).update(v)
    print()
    print("TOTAL expert tensors:", dict(tot_e))
    print("TOTAL non-expert    :", dict(tot_o))
    for k, v in sorted(tot_by.items()):
        print(f"   {k:24s} {dict(v)}")
