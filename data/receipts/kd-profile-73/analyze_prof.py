#!/usr/bin/env python3
"""PREREG_KD_PROFILE_73 analysis: analyze_prof.py CELL.sqlite CELL.jsonl > CELL.summary.json

Requests' kernels form clusters separated by > 1 s of GPU idle (the client sleeps 3 s between requests); the last
len(requests) clusters are matched to the client's requests in order. Within a cluster, with t_end = its last kernel
end, the decode window is [t_end - predicted_ms, t_end] and the prefill window the prompt_ms before it (the server's
own timings). Kernels and copies are clipped to each window."""
import json, re, sqlite3, sys
from collections import defaultdict

CATS = [("matvec", r"mul_mat_vec|quantize_q8_1|^mmv"), ("matmul", r"mul_mat_q|gemm|quantize_mmq|mmq"),
        ("attention", r"flash_attn|fattn|soft_max"), ("gdn", r"gated_delta|conv_state|ssm"),
        ("comm", r"nccl|allreduce|all_reduce"), ("convert", r"convert|cpy|dequantize")]
KINDS = {1: "HtoD", 2: "DtoH", 8: "DtoD", 10: "PtoP"}


def cat(name):
    n = name.lower()
    for c, rx in CATS:
        if re.search(rx, n):
            return c
    return "elementwise"


def union(iv):
    tot, cur_s, cur_e = 0, None, None
    for s, e in sorted(iv):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                tot += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        tot += cur_e - cur_s
    return tot


def window(K, C, w0, w1, n_tok):
    by_name, by_cat = defaultdict(float), defaultdict(float)
    by_dev_cat = defaultdict(lambda: defaultdict(float))
    iv_dev, count = defaultdict(list), 0
    for s, e, dev, name in K:
        if e <= w0 or s >= w1:
            continue
        s2, e2 = max(s, w0), min(e, w1)
        d = (e2 - s2) / 1e6
        by_name[name] += d; by_cat[cat(name)] += d; by_dev_cat[dev][cat(name)] += d
        iv_dev[dev].append((s2, e2)); count += 1
    cp = defaultdict(float); cpb = defaultdict(int)
    for s, e, dev, kind, nb in C:
        if e <= w0 or s >= w1:
            continue
        cp[KINDS.get(kind, str(kind))] += (min(e, w1) - max(s, w0)) / 1e6; cpb[KINDS.get(kind, str(kind))] += nb
    span = (w1 - w0) / 1e6
    per = lambda v: round(v / n_tok, 4) if n_tok else None
    return {
        "window_ms": round(span, 2), "n_tokens": n_tok, "kernels": count, "kernels_per_token": per(count),
        "busy_frac": {str(d): round(union(v) / 1e6 / span, 4) for d, v in sorted(iv_dev.items())},
        "ms_per_token_by_cat": {c: per(v) for c, v in sorted(by_cat.items(), key=lambda x: -x[1])},
        "ms_per_token_by_cat_dev": {str(d): {c: per(v) for c, v in sorted(dc.items(), key=lambda x: -x[1])}
                                    for d, dc in sorted(by_dev_cat.items())},
        "top_kernels_ms_per_token": [(n, per(v)) for n, v in sorted(by_name.items(), key=lambda x: -x[1])[:15]],
        "copy_ms_per_token": {k: per(v) for k, v in cp.items()}, "copy_bytes": dict(cpb),
        "matmul_kernels_in_window": sum(1 for s, e, dev, name in K if not (e <= w0 or s >= w1) and cat(name) == "matmul"),
    }


def main():
    db, jl = sys.argv[1], sys.argv[2]
    c = sqlite3.connect(db)
    K = c.execute("select k.start, k.end, k.deviceId, s.value from CUPTI_ACTIVITY_KIND_KERNEL k "
                  "join StringIds s on s.id = k.shortName order by k.start").fetchall()
    C = c.execute("select start, end, deviceId, copyKind, bytes from CUPTI_ACTIVITY_KIND_MEMCPY").fetchall()
    graphs = c.execute("select count(*) from CUPTI_ACTIVITY_KIND_RUNTIME r join StringIds s on s.id = r.nameId "
                       "where s.value like 'cudaGraphLaunch%'").fetchone()[0]
    reqs = [json.loads(l) for l in open(jl)]
    clusters, cs, ce = [], None, None
    for s, e, _, _ in K:
        if ce is None or s - ce > 1e9:
            if ce is not None:
                clusters.append((cs, ce))
            cs, ce = s, e
        else:
            ce = max(ce, e)
    clusters.append((cs, ce))
    out = {"db": db, "kernels_total": len(K), "graph_launches": graphs, "n_clusters": len(clusters), "requests": []}
    for r, (s, e) in zip(reqs, clusters[-len(reqs):]):
        t = r.get("timings") or {}
        rec = {"name": r["name"], "cluster_ms": round((e - s) / 1e6, 1), "prompt_ms": t.get("prompt_ms"),
               "predicted_ms": t.get("predicted_ms"), "prompt_n": t.get("prompt_n"), "predicted_n": t.get("predicted_n"),
               "prefill_tps": t.get("prompt_per_second"), "decode_tps": t.get("predicted_per_second")}
        if r["name"] != "warmup" and t:
            d1 = e; d0 = e - t["predicted_ms"] * 1e6; p0 = d0 - t["prompt_ms"] * 1e6
            rec["decode"] = window(K, C, d0, d1, t["predicted_n"])
            rec["prefill"] = window(K, C, p0, d0, t["prompt_n"])
        out["requests"].append(rec)
    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
