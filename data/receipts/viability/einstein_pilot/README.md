# Einstein pilot — UNSCORED

8 generations run before any scored data, to check the instrument. Excluded from every number in
the receipt. Disclosed in `PREREG_EINSTEIN_TERMINATION.md` Amendments 1 and 2.

- `iq2m/`  DavidAU `…735-882…-MTP-IQ2_M`, server `-c 16384`. Led to Amendment 1.
- `iq4xs/` base `Qwen3.8-27B-UD-IQ4_XS`, server `-c 12288`.

**Known defect, left uncorrected in the raw rows:** the runner hardcoded `n_ctx: 16384`, so the
`iq4xs/` rows record the wrong context — the server was at 12,288. Fixed in the runner (it now reads
`/slots`); corrected here rather than by rewriting the data.

The `iq4xs/` rows use seed 2001, the scored set's rep-1 seed, so 4 scored cells were previewed.
