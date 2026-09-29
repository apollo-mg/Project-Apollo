#!/usr/bin/env python3
"""Read a GGUF header over HTTP range requests; print tensor name, type id, byte size.
usage: gguf_remote_header.py URL [URL ...] > out.tsv   (sizes from offset gaps; last tensor from file size)"""
import os, struct, sys, urllib.request

TOKEN = None
tp = os.path.expanduser("~/.cache/huggingface/token")
if os.path.exists(tp):
    TOKEN = open(tp).read().strip()


def fetch(url, a, b):
    req = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b}"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=120) as r:
        total = int(r.headers.get("Content-Range", "/0").split("/")[-1])
        return r.read(), total


class Buf:
    def __init__(self, url):
        self.url, self.data, self.pos = url, b"", 0
        self.data, self.total = fetch(url, 0, 32 * 2**20 - 1)

    def need(self, n):
        while self.pos + n > len(self.data):
            more, _ = fetch(self.url, len(self.data), len(self.data) + 32 * 2**20 - 1)
            self.data += more

    def u(self, fmt):
        n = struct.calcsize(fmt); self.need(n)
        v = struct.unpack_from("<" + fmt, self.data, self.pos); self.pos += n
        return v[0]

    def s(self):
        n = self.u("Q"); self.need(n)
        v = self.data[self.pos:self.pos + n]; self.pos += n
        return v.decode("utf-8", "replace")


SCALAR = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}


def val(b, t):
    if t in SCALAR:
        return b.u(SCALAR[t])
    if t == 8:
        return b.s()
    if t == 9:
        et, n = b.u("I"), b.u("Q")
        return [val(b, et) for _ in range(n)] if n < 64 else (skip(b, et, n) or f"<array {n}>")
    raise ValueError(t)


def skip(b, et, n):
    for _ in range(n):
        val(b, et)


def main():
    want_kv = None
    if sys.argv[1] == "--kv":          # --kv KEY URL: print one metadata value (e.g. tokenizer.chat_template) and exit
        want_kv, sys.argv[1:] = sys.argv[2], sys.argv[3:]
    for url in sys.argv[1:]:
        b = Buf(url)
        assert b.data[:4] == b"GGUF", url
        b.pos = 4
        ver, nt, nkv = b.u("I"), b.u("Q"), b.u("Q")
        align = 32
        for _ in range(nkv):
            k = b.s(); t = b.u("I"); v = val(b, t)
            if k == "general.alignment":
                align = v
            if k == want_kv:
                sys.stdout.write(v if isinstance(v, str) else repr(v))
                return
        if want_kv:
            sys.exit(f"{want_kv}: not in {url}")
        tens = []
        for _ in range(nt):
            name = b.s(); nd = b.u("I"); dims = [b.u("Q") for _ in range(nd)]; typ = b.u("I"); off = b.u("Q")
            tens.append([name, typ, off, dims])
        data_start = (b.pos + align - 1) // align * align
        tens.sort(key=lambda x: x[2])
        for i, (name, typ, off, dims) in enumerate(tens):
            end = tens[i + 1][2] if i + 1 < len(tens) else b.total - data_start
            print(f"{url.rsplit('/', 1)[-1]}\t{name}\t{typ}\t{end - off}\t{'x'.join(map(str, dims))}")


if __name__ == "__main__":
    main()
