#!/usr/bin/env python3
"""Provenance manifest for every GGUF the receipts depend on.

Why this exists: 92 models named in published receipts are ALREADY gone from local disk, and
only 2 receipt files record where any model came from. Holding the bytes is weak replication
insurance -- drives fail, scratchpads get wiped -- while ~300 bytes of provenance survives in
git, travels with the receipt, and lets a third party verify they have the same file. Recording
this is what makes local deletion safe.

Fingerprint is size + sha256 of the first and last 16 MiB, not a full hash: a full sha256 of
~2 TiB is hours of I/O, while size+head+tail distinguishes any two real GGUFs (verified on the
one true duplicate found in Downloads) and costs milliseconds.

Companion files (mmproj-*, mtp-*, *imatrix*) sitting next to a cited model are included even
though no receipt names them -- they are required to reproduce a run and are exactly what a
naive "not cited -> delete" sweep destroys.

Usage: model_manifest.py <out.json> [roots...]
"""
import hashlib, json, os, re, struct, sys

CHUNK = 16 * 1024 * 1024
COMPANION = re.compile(r'(mmproj|^mtp-|imatrix|draft)', re.I)

GGUF_STR = 8


def gguf_meta(path):
    """Read arch / quant / name from the GGUF header without loading the tensors."""
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"GGUF":
                return {}
            ver = struct.unpack("<I", f.read(4))[0]
            if ver not in (2, 3):
                return {"gguf_version": ver}
            n_tensors, n_kv = struct.unpack("<QQ", f.read(16))
            out = {"gguf_version": ver, "n_tensors": n_tensors, "n_kv": n_kv}
            want = {"general.architecture", "general.name", "general.file_type",
                    "general.quantization_version", "general.basename"}
            for _ in range(n_kv):
                klen = struct.unpack("<Q", f.read(8))[0]
                key = f.read(klen).decode("utf-8", "replace")
                vt = struct.unpack("<I", f.read(4))[0]
                val = _read_val(f, vt)
                if key in want:
                    out[key] = val
            return out
    except Exception as e:
        return {"header_error": f"{type(e).__name__}: {e}"}


def _read_val(f, vt):
    simple = {0: ("<B", 1), 1: ("<b", 1), 2: ("<H", 2), 3: ("<h", 2), 4: ("<I", 4),
              5: ("<i", 4), 6: ("<f", 4), 7: ("<?", 1), 10: ("<Q", 8), 11: ("<q", 8),
              12: ("<d", 8)}
    if vt in simple:
        fmt, n = simple[vt]
        return struct.unpack(fmt, f.read(n))[0]
    if vt == GGUF_STR:
        n = struct.unpack("<Q", f.read(8))[0]
        return f.read(n).decode("utf-8", "replace")
    if vt == 9:  # array — skip, we only want scalars
        et = struct.unpack("<I", f.read(4))[0]
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            _read_val(f, et)
        return f"<array[{n}]>"
    raise ValueError(f"unknown gguf value type {vt}")


def fingerprint(path, size):
    h1, h2 = hashlib.sha256(), hashlib.sha256()
    with open(path, "rb") as f:
        h1.update(f.read(CHUNK))
        if size > CHUNK:
            f.seek(max(0, size - CHUNK))
            h2.update(f.read(CHUNK))
    return h1.hexdigest()[:32], (h2.hexdigest()[:32] if size > CHUNK else "")


def main():
    out_path = sys.argv[1]
    roots = sys.argv[2:] or ["/mnt/TG_2TB/AI/Models", "/mnt/TG_2TB/Models",
                             "/home/mark/Downloads", "/mnt/TG_2TB/kv_shootout_bases"]
    repo = "/mnt/TG_2TB/Projects/Apollo"
    cited = set()
    for sub in ("data/receipts", "data/Apollo Docs"):
        for dp, _, fns in os.walk(os.path.join(repo, sub)):
            for fn in fns:
                if not fn.endswith((".md", ".txt", ".json", ".tsv", ".log")):
                    continue
                try:
                    t = open(os.path.join(dp, fn), errors="ignore").read()
                except OSError:
                    continue
                cited.update(re.findall(r'[A-Za-z0-9._-]+\.gguf', t))

    # Pass 1: locate cited files and note their directories, so companions come along.
    keep_dirs, entries = set(), []
    found = {}
    for r in roots:
        for dp, _, fns in os.walk(r):
            for fn in fns:
                if fn.endswith(".gguf"):
                    found.setdefault(fn, []).append(os.path.join(dp, fn))
    for fn, paths in found.items():
        if fn in cited:
            for p in paths:
                keep_dirs.add(os.path.dirname(p))

    for fn, paths in sorted(found.items()):
        for p in paths:
            is_cited = fn in cited
            is_comp = COMPANION.search(fn) and os.path.dirname(p) in keep_dirs
            if not (is_cited or is_comp):
                continue
            size = os.path.getsize(p)
            head, tail = fingerprint(p, size)
            entries.append(dict(
                name=fn, path=p, bytes=size,
                gib=round(size / 2**30, 2),
                reason="cited" if is_cited else "companion-of-cited",
                head_sha256_16MiB=head, tail_sha256_16MiB=tail,
                **gguf_meta(p)))
            print(f"  {entries[-1]['gib']:>7.2f} GiB  {entries[-1]['reason']:<18} {fn[:58]}",
                  flush=True)

    json.dump({"generated_for": "replication provenance; see COMMITMENTS.md D-items",
               "fingerprint": "sha256 of first and last 16 MiB + exact byte size",
               "n": len(entries), "total_gib": round(sum(e["bytes"] for e in entries) / 2**30, 1),
               "entries": entries}, open(out_path, "w"), indent=1)
    print(f"\n{len(entries)} entries, {sum(e['bytes'] for e in entries)/2**30:.1f} GiB -> {out_path}")


main()
