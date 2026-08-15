#!/usr/bin/env python3
"""Per-tensor probe of the MTP draft head (blk.64) across a remote GGUF ladder.

gguf_librarian.read_gguf() aggregates the tensor table into type counters and
drops the names, which is right for its job (expert census) and wrong for this
one. Same HTTP-range trick, but we keep the names for one block.

Reports, per file: the blk.64 recipe tensor-by-tensor, plus the body histogram
for context, so a "the head is pinned while the body scales" pattern is visible
without downloading a byte of weights.
"""
import collections, struct, sys, urllib.parse
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo")
from modules.gguf_librarian import _HTTPFile, _val, TRAITS, hf_files


def head_probe(url, block="blk.64."):
    f = _HTTPFile(url)
    if f.read(4) != b"GGUF":
        return {"error": "not a GGUF"}
    struct.unpack("<I", f.read(4))[0]
    n_tensors, n_kv = struct.unpack("<QQ", f.read(16))
    kv = {}
    for _ in range(n_kv):
        klen = struct.unpack("<Q", f.read(8))[0]
        key = f.read(klen).decode("utf-8", "replace")
        vt = struct.unpack("<I", f.read(4))[0]
        v = _val(f, vt)
        if not isinstance(v, list) or len(v) <= 8:
            kv[key] = v
    arch = kv.get("general.architecture", "?")
    head, body, exps = [], collections.Counter(), collections.Counter()
    head_bytes = 0
    for _ in range(n_tensors):
        nlen = struct.unpack("<Q", f.read(8))[0]
        tname = f.read(nlen).decode("utf-8", "replace")
        nd = struct.unpack("<I", f.read(4))[0]
        ne = [struct.unpack("<Q", f.read(8))[0] for _ in range(nd)]
        ty = struct.unpack("<I", f.read(4))[0]
        struct.unpack("<Q", f.read(8))
        tn, blk, tsz = TRAITS.get(ty, (f"type{ty}", 0, 0))
        if tname.startswith(block):
            nb = 0
            if blk:
                nb = (ne[0] // blk) * tsz
                for d in ne[1:]:
                    nb *= d
            head.append((tname, tn, tuple(ne), nb))
            head_bytes += nb
        elif ("_exps" in tname or "_chexps" in tname) and nd == 3 and blk:
            exps[tn] += 1
        else:
            body[tn] += 1
    return {"arch": arch, "block_count": kv.get(f"{arch}.block_count"),
            "n_tensors": n_tensors, "head": head, "head_bytes": head_bytes,
            "body": dict(body), "experts": dict(exps),
            "bytes": f.size, "fetched": f.fetched}


def hist(c, top=8):
    it = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))
    s = " + ".join(f"{t}x{n}" for t, n in it[:top])
    return s + (f" + {len(it)-top} more" if len(it) > top else "")


def main():
    repo = sys.argv[1]
    only = sys.argv[2] if len(sys.argv) > 2 else None
    files = sorted(x for x in hf_files(repo) if x.endswith(".gguf"))
    if only:
        import re
        files = [x for x in files if re.search(only, x, re.I)]
    tot = 0
    print(f"=== {repo}  ({len(files)} files) ===")
    for fn in files:
        url = f"https://huggingface.co/{repo}/resolve/main/" + urllib.parse.quote(fn)
        try:
            m = head_probe(url)
        except Exception as e:
            print(f"\n{fn}\n  ERROR {type(e).__name__}: {e}")
            continue
        if "error" in m:
            print(f"\n{fn}\n  {m['error']}")
            continue
        tot += m["fetched"]
        print(f"\n{fn}   {m['bytes']/2**30:.2f} GiB  "
              f"[{m['n_tensors']} tensors, block_count={m['block_count']}, "
              f"{m['fetched']/2**20:.1f} MiB read]")
        print(f"  body    {hist(collections.Counter(m['body']))}")
        if m["experts"]:
            print(f"  experts {hist(collections.Counter(m['experts']))}")
        if not m["head"]:
            print("  HEAD    *** no blk.64 tensors — no MTP draft head in this file ***")
            continue
        print(f"  HEAD    {len(m['head'])} tensors, {m['head_bytes']/2**20:.2f} MiB")
        for name, ty, ne, nb in m["head"]:
            print(f"      {name:<34} {ty:<8} {str(list(ne)):<20} {nb/2**20:8.2f} MiB")
    print(f"\ntotal transferred {tot/2**20:.1f} MiB")


if __name__ == "__main__":
    main()
