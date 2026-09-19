#!/usr/bin/env python3
"""Score P-L0 from a llama-perplexity --kl-divergence log.

Prints the KLD block VERBATIM first, then the parsed values, then the verdict.
The verbatim dump is deliberate: every instrument defect this campaign has hit came from
trusting a derived view over the raw one. llama-perplexity exits 0 on failure, so the
absence of a parsed block is itself the failure signal.
"""
import re, sys

log = open(sys.argv[1], errors="replace").read()

print("=" * 72)
print("RAW TAIL (last 40 lines)")
print("=" * 72)
print("\n".join(log.splitlines()[-40:]))

m = re.search(r"={3,}\s*KL divergence statistics\s*={3,}(.*?)(?:\n\n|\Z)", log, re.S | re.I)
if m:
    print("=" * 72); print("KLD BLOCK VERBATIM"); print("=" * 72)
    print(m.group(1).strip())

def grab(pat):
    mm = re.search(pat, log, re.I)
    return mm.group(1) if mm else None

vals = {
    "mean_kld":   grab(r"Mean\s+KLD:\s*([0-9.eE+-]+)"),
    "median_kld": grab(r"Median\s+KLD:\s*([0-9.eE+-]+)"),
    "p99_kld":    grab(r"99\.0%\s+KLD:\s*([0-9.eE+-]+)"),
    "max_kld":    grab(r"Maximum\s+KLD:\s*([0-9.eE+-]+)"),
    "same_top":   grab(r"Same\s+top\s+p:\s*([0-9.eE+-]+)"),
}
print("=" * 72); print("PARSED"); print("=" * 72)
for k, v in vals.items():
    print(f"  {k:<12} {v if v is not None else 'NOT FOUND'}")

if vals["mean_kld"] is None or vals["same_top"] is None:
    print("\nVERDICT: NO RESULT -- the run did not produce a KLD block.")
    print("         (rc is meaningless here; llama-perplexity exits 0 on failure.)")
    sys.exit(2)

mean = float(vals["mean_kld"]); top = float(vals["same_top"])
ok = (mean < 1e-4) and (top >= 99.9)
print(f"\n  gate: mean KLD {mean:.3e} < 1e-4  -> {mean < 1e-4}")
print(f"  gate: same-top {top:.4f}% >= 99.9% -> {top >= 99.9}")
print(f"\nVERDICT: P-L0 {'PASS' if ok else 'FAIL'}")
print(f"\nNOTE: this measured mean KLD ({mean:.3e}) is the reproducibility FLOOR that")
print("      P-L5 is scored against. The prereg writes P-L5's threshold as 1e-4, but the")
print("      real floor is whatever this run just measured.")
sys.exit(0 if ok else 1)
