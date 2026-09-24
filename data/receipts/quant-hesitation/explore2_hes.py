#!/usr/bin/env python3
"""EXPLORATORY, second pass (not registered). Runs on .194 next to the base (reads only its token header).
usage: explore2_hes.py BASE REF_GGUF DUMPDIR H.npy OUT.json OUT.npz
  export  OUT.npz: tokens (n_chunk x n_ctx int32), per scored position: nxt, hes, digit, sstart masks. With
          raw/dumps and raw/EXPLORE_hes.H.npy this reproduces every number without the 62 GB base.
  E6      the source's own statistic: mean KLD per next-token TYPE (>= 50 occurrences), top-20 and bottom-20,
          'largest high' / 'largest low' (Lotfi et al.: 1.30 / 0.015 ~ 100x on R1-Distill-1.5B, 3-bit AWQ).
  E7      sentence-start confound: SSTART = non-HES positions whose context token ends a sentence or line and whose
          next token starts with a capital letter. (a) SSTART vs its 20 nearest OTHER-non-SSTART neighbours in H;
          (b) HES vs its 20 nearest SSTART neighbours in H. Chunk bootstrap, 500 resamples, fixed match sets."""
import json, re, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path.home() / "buun-llama-cpp/gguf-py"))
from gguf import GGUFReader

BASE, REF, DUMPDIR, HNPY, OUT, NPZ = sys.argv[1:7]
MARKERS = {"Wait", "But", "Hmm", "Actually", "Alternatively", "However", "Hold", "Oh", "Maybe", "Perhaps"}
ARMS = ["Q2KXL", "IQ3XXS", "IQ4XS", "Q4KM", "Q6K"]

def bytes_to_unicode():
    bs = list(range(33, 127)) + list(range(161, 173)) + list(range(174, 256)); cs = bs[:]; n = 0
    for b in range(256):
        if b not in bs: bs.append(b); cs.append(256 + n); n += 1
    return {chr(c): b for b, c in zip(bs, cs)}
U2B = bytes_to_unicode()
def dec(t):
    try: return bytes(U2B[c] for c in t).decode("utf-8", "replace")
    except KeyError: return t

with open(BASE, "rb") as fh:
    assert fh.read(8) == b"_logits_"
    n_ctx, n_vocab, n_chunk = (int(x) for x in np.frombuffer(fh.read(12), dtype=np.int32))
    toks = np.frombuffer(fh.read(4 * n_chunk * n_ctx), dtype=np.int32).reshape(n_chunk, n_ctx).copy()
first = n_ctx // 2; n_pos = n_ctx - 1 - first
H = np.load(HNPY); assert len(H) == n_chunk * n_pos

r = GGUFReader(REF); f = r.fields["tokenizer.ggml.tokens"]
vocab = [dec(bytes(f.parts[i]).decode("utf-8", "replace")) for i in f.data]
is_hes = np.array([t.strip() in MARKERS for t in vocab])
is_dig = np.array([len(t.strip()) == 1 and t.strip() in "0123456789" for t in vocab])
ends_sent = np.array([bool(re.search(r"[.?!][\"')\]]*\s*$", t)) or t.endswith("\n") for t in vocab])
starts_cap = np.array([bool(re.match(r"[A-Z]", t.lstrip())) for t in vocab])

cur = toks[:, first:first + n_pos].reshape(-1)          # last context token at each scored position
nxt = toks[:, first + 1:first + 1 + n_pos].reshape(-1)  # token being predicted
hes, dig = is_hes[nxt], is_dig[nxt]
sstart = ends_sent[cur] & starts_cap[nxt] & ~hes
chunk_of = np.repeat(np.arange(n_chunk), n_pos)
np.savez_compressed(NPZ, tokens=toks, nxt=nxt, hes=hes, digit=dig, sstart=sstart,
                    n_ctx=n_ctx, n_chunk=n_chunk, first=first)

def load_dump(a):
    b = np.fromfile(Path(DUMPDIR) / f"{a}.kld.bin", dtype=np.uint8)
    return np.frombuffer(b[8:].tobytes(), dtype=np.float32).astype(np.float64)
K = {a: load_dump(a) for a in ARMS}

res = {"n_hes": int(hes.sum()), "n_sstart": int(sstart.sum()),
       "hes_frac_after_sentence_end": float((ends_sent[cur] & hes).sum() / hes.sum()),
       "meanH": {"hes": float(H[hes].mean()), "sstart": float(H[sstart].mean()), "other": float(H[~hes].mean())}}

# E6: per-type mean KLD, >= 50 occurrences
cnt = np.bincount(nxt, minlength=len(vocab))
elig = np.nonzero(cnt >= 50)[0]
res["E6"] = {"n_types_eligible": int(len(elig))}
for a in ARMS:
    s = np.bincount(nxt, weights=K[a], minlength=len(vocab)); hs = np.bincount(nxt, weights=H, minlength=len(vocab))
    m = s[elig] / cnt[elig]; order = np.argsort(m)
    top, bot = elig[order[::-1][:20]], elig[order[:20]]
    row = lambda t: {"tok": vocab[t], "n": int(cnt[t]), "kld": float(s[t] / cnt[t]), "H": float(hs[t] / cnt[t]),
                     "marker": bool(is_hes[t])}
    res["E6"][a] = {"largest_high": float(m[order[-1]]), "largest_low": float(m[order[19]]),
                    "range_ratio": float(m[order[-1]] / m[order[19]]),
                    "markers_in_top20": int(is_hes[top].sum()), "markers_eligible": int(is_hes[elig].sum()),
                    "marker_ranks": {vocab[t]: int(np.nonzero(elig[order[::-1]] == t)[0][0]) + 1
                                     for t in elig if is_hes[t]},
                    "top20": [row(t) for t in top], "bottom20": [row(t) for t in bot]}

# E7: sentence-start confound
rng = np.random.default_rng(2)
W = np.stack([np.bincount(rng.integers(0, n_chunk, n_chunk), minlength=n_chunk) for _ in range(500)]).astype(float)
def nn_match(src_mask, pool_mask, k=20):
    p_idx = np.nonzero(pool_mask)[0]; order = np.argsort(H[p_idx]); pH = H[p_idx][order]; ps = p_idx[order]
    s_idx = np.nonzero(src_mask)[0]; j = np.searchsorted(pH, H[s_idx])
    out = np.empty((len(s_idx), k), dtype=np.int64)
    for n, (i, jj) in enumerate(zip(s_idx, j)):
        lo, hi = max(0, jj - k), min(len(pH), jj + k); c = np.arange(lo, hi)
        out[n] = ps[c[np.argsort(np.abs(pH[c] - H[i]))[:k]]]
    return s_idx, out
def nn_ratio(k, s_idx, nn):
    hk, nk, ch = k[s_idx], k[nn].mean(1), chunk_of[s_idx]
    bs = [(w[ch] * hk).sum() / (w[ch] * nk).sum() for w in W]
    return [float(hk.mean() / nk.mean()), [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]]
sa, nna = nn_match(sstart, ~hes & ~sstart)
sb, nnb = nn_match(hes, sstart)
res["E7_dH"] = {"a": float(np.abs(H[nna] - H[sa][:, None]).mean()), "b": float(np.abs(H[nnb] - H[sb][:, None]).mean())}
res["E7a_sstart_vs_other"] = {a: nn_ratio(K[a], sa, nna) for a in ARMS}
res["E7b_hes_vs_sstart"] = {a: nn_ratio(K[a], sb, nnb) for a in ARMS}
Path(OUT).write_text(json.dumps(res, indent=1, ensure_ascii=False))
print(json.dumps({k: v for k, v in res.items() if k != "E6"}, indent=1))
for a in ["Q2KXL", "IQ3XXS"]:
    e = res["E6"][a]
    print(a, "largest_high", round(e["largest_high"], 4), "largest_low", round(e["largest_low"], 5),
          "ratio", round(e["range_ratio"], 1), "markers in top20", e["markers_in_top20"], "of eligible", e["markers_eligible"],
          "ranks", e["marker_ranks"])
    print("  top20:", [(x["tok"], round(x["kld"], 3), round(x["H"], 2)) for x in e["top20"]])
    print("  bottom20:", [(x["tok"], round(x["kld"], 5)) for x in e["bottom20"]])
print("eligible types", res["E6"]["n_types_eligible"])
