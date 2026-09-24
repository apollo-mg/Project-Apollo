#!/usr/bin/env python3
"""EXPLORATORY robustness checks for RESULT_HESITATION_KLD.md (not registered; analyze_hes.py is the registered scorer).
usage: explore_hes.py BASE REF_GGUF DUMPDIR OUT.json [WORKERS]
Same base/dump layouts and the same float64 entropy as analyze_hes.py (verified: the decile edges must reproduce
RESULT_hes.json exactly). Saves per-position entropy H and reference top-1 prob P1 next to OUT as .npy.
  E1  within-decile mean entropy, HES vs OTHER (how good is the registered matching?)
  E2  entropy-matched ratio at 50 and 100 quantile bins, chunk-bootstrap CI (2,000 resamples)
  E3  nearest-neighbour matching: each HES position vs the 20 OTHER positions closest in H
  E4  the source's comparison class: KLD at HES vs at positions whose next token is a digit
  E5  matching on reference top-1 probability instead of entropy (10 and 50 bins)"""
import json, sys, numpy as np
from multiprocessing import Pool
from pathlib import Path
sys.path.insert(0, str(Path.home() / "buun-llama-cpp/gguf-py"))
from gguf import GGUFReader

BASE, REF, DUMPDIR, OUT = sys.argv[1:5]
WORKERS = int(sys.argv[5]) if len(sys.argv) > 5 else 16
MARKERS = {"Wait", "But", "Hmm", "Actually", "Alternatively", "However", "Hold", "Oh", "Maybe", "Perhaps"}
ARMS = ["Q2KXL", "IQ3XXS", "IQ4XS", "Q4KM", "Q6K"]
B = 2000

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
    toks = np.frombuffer(fh.read(4 * n_chunk * n_ctx), dtype=np.int32).reshape(n_chunk, n_ctx)
    HDR = fh.tell()
NV = 2 * ((n_vocab + 1) // 2) + 4
first = n_ctx // 2; n_pos = n_ctx - 1 - first
NROWS = n_chunk * n_pos

def ent_block(s):  # identical arithmetic to analyze_hes.py
    mm = np.memmap(BASE, dtype=np.uint16, mode="r", offset=HDR, shape=(NROWS, NV))
    blk = np.array(mm[s:s + 256])
    fl = blk[:, :4].copy().view(np.float32)
    scale, mn = fl[:, 0:1].astype(np.float64), fl[:, 1:2].astype(np.float64)
    q = blk[:, 4:4 + n_vocab].astype(np.float64)
    lp = np.where(q > 0, mn + scale * q, -np.inf)
    p = np.exp(lp); p /= p.sum(1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        h = -np.nansum(np.where(p > 0, p * np.log(p), 0), 1)
    return s, h, p.max(1)

if __name__ == "__main__":
    out = Path(OUT); hp, pp = out.with_suffix(".H.npy"), out.with_suffix(".P1.npy")
    if hp.exists() and pp.exists():
        H, P1 = np.load(hp), np.load(pp)
    else:
        H = np.empty(NROWS); P1 = np.empty(NROWS)
        with Pool(WORKERS) as pool:
            for k, (s, h, p1) in enumerate(pool.imap_unordered(ent_block, range(0, NROWS, 256))):
                H[s:s + len(h)] = h; P1[s:s + len(p1)] = p1
                if k % 50 == 0: print(f"entropy block {k}/{(NROWS + 255) // 256}", flush=True)
        np.save(hp, H); np.save(pp, P1)

    r = GGUFReader(REF); f = r.fields["tokenizer.ggml.tokens"]
    vocab = [dec(bytes(f.parts[i]).decode("utf-8", "replace")) for i in f.data]
    is_hes = np.array([t.strip() in MARKERS for t in vocab])
    is_dig = np.array([len(t.strip()) == 1 and t.strip() in "0123456789" for t in vocab])
    nxt = toks[:, first + 1:first + 1 + n_pos].reshape(-1)
    hes, dig = is_hes[nxt], is_dig[nxt]
    oth = ~hes
    chunk_of = np.repeat(np.arange(n_chunk), n_pos)
    reg = json.load(open(Path(DUMPDIR).parent / "RESULT_hes.json")) if (Path(DUMPDIR).parent / "RESULT_hes.json").exists() else None

    def load_dump(a):
        b = np.fromfile(Path(DUMPDIR) / f"{a}.kld.bin", dtype=np.uint8)
        npos, nch = np.frombuffer(b[:8].tobytes(), dtype=np.int32)
        assert npos == n_pos and nch == n_chunk
        return np.frombuffer(b[8:].tobytes(), dtype=np.float32).astype(np.float64)
    K = {a: load_dump(a) for a in ARMS}

    def qbins(x, nb):
        e = np.quantile(x, np.linspace(0, 1, nb + 1)); e[-1] += 1e-9
        return np.clip(np.searchsorted(e, x, side="right") - 1, 0, nb - 1), e

    res = {"n_hes": int(hes.sum()), "n_digit": int(dig.sum()), "n_pos": int(NROWS)}
    dbin, dedges = qbins(H, 10)
    if reg: res["decile_edges_match_registered"] = bool(np.allclose(dedges, reg["decile_edges"], rtol=0, atol=1e-12))

    # E1: residual entropy gap inside the registered deciles
    res["E1_within_decile_meanH"] = [{"decile": d, "n_hes": int(((dbin == d) & hes).sum()),
        "H_hes": float(H[(dbin == d) & hes].mean()) if ((dbin == d) & hes).any() else None,
        "H_other": float(H[(dbin == d) & oth].mean())} for d in range(10)]

    rng = np.random.default_rng(1)
    W = np.stack([np.bincount(rng.integers(0, n_chunk, n_chunk), minlength=n_chunk) for _ in range(B)]).astype(np.float64)

    def matched(k, bins, nb, cls=hes, ref=oth):
        """pooled ratio sum_b nh_b*mean_cls_b / sum_b nh_b*mean_ref_b, point + chunk-bootstrap CI (vectorized)."""
        idx_c = chunk_of * nb + bins
        def agg(mask, v): return np.bincount(idx_c[mask], weights=v[mask], minlength=n_chunk * nb).reshape(n_chunk, nb)
        Sc, Nc = agg(cls, k), agg(cls, np.ones_like(k)); Sr, Nr = agg(ref, k), agg(ref, np.ones_like(k))
        def ratio(Wm):
            sc, nc, sr, nr = Wm @ Sc, Wm @ Nc, Wm @ Sr, Wm @ Nr
            ok = (nc > 0) & (nr > 0)
            with np.errstate(divide="ignore", invalid="ignore"):
                num = np.where(ok, sc, 0).sum(-1); den = np.where(ok, nc * sr / np.where(nr > 0, nr, 1), 0).sum(-1)
            return num / den
        pt = float(ratio(np.ones((1, n_chunk)))[0]); bs = ratio(W)
        return pt, [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]

    b50, _ = qbins(H, 50); b100, _ = qbins(H, 100)
    pb10, _ = qbins(-P1, 10); pb50, _ = qbins(-P1, 50)
    res["E2_entropy_bins"], res["E5_top1prob_bins"], res["E3_nn20"], res["E4_digits"] = {}, {}, {}, {}
    # E3: nearest neighbours in H among OTHER (fixed match set)
    o_idx = np.nonzero(oth)[0]; order = np.argsort(H[o_idx]); oH = H[o_idx][order]; o_sorted = o_idx[order]
    nn = []
    for i in np.nonzero(hes)[0]:
        j = np.searchsorted(oH, H[i]); lo, hi = max(0, j - 20), min(len(oH), j + 20)
        cand = np.arange(lo, hi); cand = cand[np.argsort(np.abs(oH[cand] - H[i]))[:20]]
        nn.append(o_sorted[cand])
    nn = np.array(nn); h_idx = np.nonzero(hes)[0]
    res["E3_mean_abs_dH"] = float(np.abs(H[nn] - H[h_idx][:, None]).mean())
    for a in ARMS:
        k = K[a]
        res["E2_entropy_bins"][a] = {"bins10": matched(k, dbin, 10), "bins50": matched(k, b50, 50),
                                     "bins100": matched(k, b100, 100)}
        res["E5_top1prob_bins"][a] = {"bins10": matched(k, pb10, 10), "bins50": matched(k, pb50, 50)}
        hk, nk = k[h_idx], k[nn].mean(1)
        bs = []
        ch = chunk_of[h_idx]
        for w in W[:500]:
            ww = w[ch]; bs.append((ww * hk).sum() / (ww * nk).sum())
        res["E3_nn20"][a] = [float(hk.mean() / nk.mean()), [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]]
        res["E4_digits"][a] = {"kld_hes": float(k[hes].mean()), "kld_digit": float(k[dig].mean()),
                               "hes_over_digit": float(k[hes].mean() / k[dig].mean())}
    res["E4_meanH"] = {"hes": float(H[hes].mean()), "digit": float(H[dig].mean()), "other": float(H[oth].mean())}
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "E1_within_decile_meanH"}, indent=1))
    for row in res["E1_within_decile_meanH"]: print(row)
