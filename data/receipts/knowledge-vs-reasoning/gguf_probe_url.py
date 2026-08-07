#!/usr/bin/env python3
"""Probe a REMOTE GGUF's header over HTTP range requests — no full download.

Same trick that established the Maple ternary structure from a 400 GB repo without fetching a
shard. GGUF puts KV metadata and tensor-info records at the front, so a few MB answers questions
that would otherwise cost the whole file.

Here it answers one question for jabba: is the published
`DeepSeek-V4-Flash-REAP-...-chat-v2.gguf` the IMATRIX-quantized artifact, or the pre-imatrix
template his own script writes at step 0 under nearly the same name? Size cannot distinguish them
(imatrix changes which values land where, not block layout) but provenance KVs can.

Caveat recorded up front: jabba quantized with antirez/ds4 gguf-tools, NOT llama.cpp. The
`quantize.imatrix.*` KVs are a llama.cpp convention. Absence is therefore NOT proof the imatrix was
skipped — it may simply mean ds4 does not write those keys. A POSITIVE finding is conclusive; a
negative one is not, and is reported as such.
"""
import struct, sys, collections, urllib.request

sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/knowledge-vs-reasoning")
from gguf_probe import R, GGML, U32, U64, INTEREST

CHUNK = 8 << 20


class RangeFile:
    """Minimal file-like object backed by HTTP Range requests, fetched lazily in chunks."""

    def __init__(self, url):
        self.url = url
        self.pos = 0
        self.buf = b""
        self.buf_start = 0
        self.fetched = 0

    def _get(self, start, end):
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            if r.status not in (200, 206):
                raise IOError(f"HTTP {r.status}")
            data = r.read()
        self.fetched += len(data)
        return data

    def read(self, n):
        while self.pos + n > self.buf_start + len(self.buf):
            need_from = self.buf_start + len(self.buf)
            self.buf += self._get(need_from, need_from + CHUNK - 1)
        off = self.pos - self.buf_start
        out = self.buf[off:off + n]
        self.pos += n
        # keep the buffer from growing without bound
        if off > 4 * CHUNK:
            self.buf = self.buf[off:]
            self.buf_start = self.pos
        return out


def probe_url(url, label):
    print("=" * 78)
    print(label)
    print("=" * 78)
    f = RangeFile(url)
    r = R(f)
    if r.raw(4) != b"GGUF":
        print("  !! not a GGUF (or the URL served HTML — check redirects)")
        return
    ver, n_tensors, n_kv = r.fix(U32), r.fix(U64), r.fix(U64)
    print(f"  gguf v{ver}  tensors={n_tensors}  kv={n_kv}")

    kv = {}
    for _ in range(n_kv):
        k = r.string()
        kv[k] = r.value(r.fix(U32))

    print("  -- KV (filtered) --")
    for k in sorted(kv):
        if any(t in k.lower() for t in INTEREST):
            print(f"     {k:52s} = {str(kv[k])[:60]}")

    imat = sorted(k for k in kv if "imatrix" in k.lower())
    print(f"\n  >> imatrix provenance KVs: {len(imat)}")
    for k in imat:
        print(f"       {k} = {str(kv[k])[:70]}")
    if not imat:
        print("       (none — see caveat: ds4 tooling may not write llama.cpp's keys)")

    hist = collections.Counter()
    experts = {}
    for _ in range(n_tensors):
        name = r.string()
        nd = r.fix(U32)
        dims = [r.fix(U64) for _ in range(nd)]
        tt = r.fix(U32)
        r.fix(U64)
        hist[GGML.get(tt, f"type_{tt}")] += 1
        if "exps" in name and len(experts) < 3:
            experts[name] = dims

    print("\n  -- tensor type histogram --")
    for t, n in sorted(hist.items(), key=lambda x: -x[1]):
        print(f"     {t:10s} {n:6d}")
    print("  -- sample expert tensors (shape proves the retained expert count) --")
    for name, dims in experts.items():
        print(f"     {name:46s} {dims}")
    print(f"\n  bytes fetched: {f.fetched/1e6:.1f} MB of a multi-GB file")
    return kv, hist


if __name__ == "__main__":
    probe_url(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1])
