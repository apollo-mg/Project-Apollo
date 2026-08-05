#!/usr/bin/env python3
"""Audit a community TQ GGUF on HuggingFace WITHOUT downloading it.

GGUF stores all metadata (KVs + the full tensor-info block) at the head of the file, so an HTTP
range request for the first few MB is enough to read every tensor's declared type and offset.
From consecutive offsets we derive the ACTUAL on-disk bytes-per-block, which reveals the true
format regardless of what the declared id claims.

Why this matters: TheTom's fork renumbered TQ types (TQ4_1S was 45 during 2026-04-01..04-03, is 46
now; TQ3_1S was 44, is 45). Files quantized in a drift window are read as the wrong type by current
builds, compute wrong offsets, and fail to load with "failed to read tensor data" -- which looks
exactly like a corrupt download. See TQ_ENUM_DRIFT_INTEROP.md.

Usage: hf_tq_probe.py <repo-id> [more repos...]
"""
import json, struct, sys, urllib.request, io

U8, I8, U16, I16, U32, I32, F32, BOOL, STR, ARR, U64, I64, F64 = range(13)
FIXED = {U8: "<B", I8: "<b", U16: "<H", I16: "<h", U32: "<I", I32: "<i",
         F32: "<f", BOOL: "<?", U64: "<Q", I64: "<q", F64: "<d"}
SIZE = {U8: 1, I8: 1, U16: 2, I16: 2, U32: 4, I32: 4, F32: 4, BOOL: 1, U64: 8, I64: 8, F64: 8}

# TheTom fork, current numbering
KNOWN = {0: "F32", 1: "F16", 8: "Q8_0", 12: "Q4_K", 14: "Q6_K", 30: "BF16",
         41: "Q1_0", 42: "Q2_0", 43: "TURBO2_0", 44: "TURBO3_0",
         45: "TQ3_1S", 46: "TQ4_1S", 47: "TURBO4_0"}
# expected bytes per 32 values, current numbering
EXPECT_BPB = {45: 16.0, 46: 20.0, 8: 34.0, 12: 18.0, 14: 26.25}


def get(url, nbytes=None):
    req = urllib.request.Request(url, headers={"User-Agent": "gguf-header-probe"})
    if nbytes:
        req.add_header("Range", "bytes=0-%d" % (nbytes - 1))
    return urllib.request.urlopen(req, timeout=60).read()


def rd(f, n):
    b = f.read(n)
    if len(b) != n:
        raise EOFError("header truncated -- refetch with a larger range")
    return b


def rstr(f):
    (n,) = struct.unpack("<Q", rd(f, 8))
    return rd(f, n).decode("utf-8", "replace")


def skipval(f, t):
    if t == STR:
        rstr(f); return None
    if t == ARR:
        (et,) = struct.unpack("<I", rd(f, 4))
        (n,) = struct.unpack("<Q", rd(f, 8))
        if et == STR:
            for _ in range(n):
                rstr(f)
        else:
            rd(f, SIZE[et] * n)
        return None
    return struct.unpack(FIXED[t], rd(f, SIZE[t]))[0]


def probe(repo):
    print("=" * 74)
    print("REPO %s" % repo)
    try:
        meta = json.loads(get("https://huggingface.co/api/models/%s" % repo).decode())
    except Exception as e:
        print("  API error: %s" % e); return
    ggufs = [s["rfilename"] for s in meta.get("siblings", [])
             if s["rfilename"].lower().endswith(".gguf")]
    if not ggufs:
        print("  no .gguf files"); return
    # first shard alphabetically is normally 00001-of-N
    fn = sorted(ggufs)[0]
    print("  %d gguf file(s); probing %s" % (len(ggufs), fn))
    url = "https://huggingface.co/%s/resolve/main/%s" % (repo, fn)

    for size in (4 << 20, 16 << 20, 48 << 20):
        try:
            head = get(url, size)
            f = io.BytesIO(head)
            if rd(f, 4) != b"GGUF":
                print("  not a GGUF"); return
            ver, ntensor, nkv = struct.unpack("<IQQ", rd(f, 20))
            for _ in range(nkv):
                rstr(f)
                (t,) = struct.unpack("<I", rd(f, 4))
                skipval(f, t)
            tensors = []
            for _ in range(ntensor):
                name = rstr(f)
                (nd,) = struct.unpack("<I", rd(f, 4))
                dims = struct.unpack("<%dQ" % nd, rd(f, 8 * nd))
                (ty,) = struct.unpack("<I", rd(f, 4))
                (off,) = struct.unpack("<Q", rd(f, 8))
                ne = 1
                for d in dims:
                    ne *= d
                tensors.append((off, name, ty, ne))
            break
        except EOFError:
            continue
    else:
        print("  header larger than 48 MB -- skipped"); return

    print("  gguf_v%d  tensors=%d" % (ver, ntensor))
    tensors.sort()
    seen = {}
    for i in range(len(tensors) - 1):
        off, name, ty, ne = tensors[i]
        if ne == 0:
            continue
        raw = tensors[i + 1][0] - off
        bpb = raw * 32.0 / ne
        seen.setdefault(ty, []).append(bpb)

    for ty in sorted(seen):
        vals = seen[ty]
        # modal value, ignoring alignment noise on tiny tensors
        bpb = max(set(round(v, 3) for v in vals), key=lambda v: sum(1 for x in vals if round(x, 3) == v))
        nm = KNOWN.get(ty, "UNKNOWN(%d)" % ty)
        flag = ""
        if ty in EXPECT_BPB:
            if abs(bpb - EXPECT_BPB[ty]) > 0.01:
                flag = "  <<< MISMATCH: id %d should be %.2f B/32" % (ty, EXPECT_BPB[ty])
                if abs(bpb - 20.0) < 0.01 and ty == 45:
                    flag += "  => actually TQ4_1S; ENUM-DRIFT FILE, needs id 45->46"
        if ty in (45, 46) or flag:
            print("    id %-3d %-12s n=%-4d %.3f B/32 (%.2f bpw)%s"
                  % (ty, nm, len(vals), bpb, bpb * 8 / 32.0, flag))


if __name__ == "__main__":
    for r in sys.argv[1:]:
        try:
            probe(r)
        except Exception as e:
            print("  FAILED: %s" % e)
