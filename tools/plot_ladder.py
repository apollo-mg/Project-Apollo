#!/usr/bin/env python3
"""Plot the low-bit codec ladder: KLD vs SCORED bytes per weight.

Scored bytes = file minus the MTP draft head llama-perplexity ignores, so the x-axis is the
size that actually bought the measured quality. See METHOD_SCORED_BYTES.md.
"""
import json, sys, argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NPARAM = 27.21e9
MTP = {"G-IQ2XS":348469248,"G-IQ3XXS":348469248,"C-XBIN":348469248,
       "A-IQ2XS":292067328,"A-IQ3XXS":292067328,"A-IQ3S":292067328,
       "B-PTQ1":0,"B-PQ2":0}
FAM = {"G-IQ2XS":"GSQ-RCO","G-IQ3XXS":"GSQ-RCO","A-IQ2XS":"AD","A-IQ3XXS":"AD",
       "A-IQ3S":"AD","B-PTQ1":"Bonsai 2","B-PQ2":"Bonsai 2"}
STYLE = {"GSQ-RCO":("#2563eb","o"),"AD":("#dc2626","s"),"Bonsai 2":("#059669","^")}

ap = argparse.ArgumentParser(); ap.add_argument("results", nargs="+")
ap.add_argument("-o", default="ladder.png"); a = ap.parse_args()

cells = {}
for p in a.results:
    for line in open(p):
        line=line.strip()
        if line:
            d=json.loads(line)
            if d.get("status")=="OK" and d["cell"] in FAM:
                cells[d["cell"]]=d

pts={}
for c,d in cells.items():
    nb=int(d["bytes"])-MTP.get(c,0)
    pts[c]=(nb*8/NPARAM, float(d["mean_kld"]), float(d["same_top"]))

fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13,5.6))

for fam,(col,mk) in STYLE.items():
    fc=sorted([c for c in pts if FAM[c]==fam], key=lambda c: pts[c][0])
    if not fc: continue
    xs=[pts[c][0] for c in fc]; ys=[pts[c][1] for c in fc]; ts=[pts[c][2] for c in fc]
    ax.plot(xs, ys, marker=mk, color=col, label=fam, lw=2, ms=9)
    ax2.plot(xs, ts, marker=mk, color=col, label=fam, lw=2, ms=9)
    for c in fc:
        x,y,t=pts[c]
        ax.annotate(c, (x,y), textcoords="offset points", xytext=(7,6), fontsize=8, color=col)
        ax2.annotate(c, (x,t), textcoords="offset points", xytext=(7,-11), fontsize=8, color=col)

# matched-size illustration: GSQ curve priced at each AD size
g=sorted([c for c in pts if FAM[c]=="GSQ-RCO"], key=lambda c: pts[c][0])
if len(g)>=2:
    (b1,k1,_),(b2,k2,_) = pts[g[0]], pts[g[-1]]
    rate=(k1-k2)/(b2-b1)
    for c in [c for c in pts if FAM[c]=="AD"]:
        x,y,_=pts[c]; pred=k1-(x-b1)*rate
        if pred>0:
            ax.plot([x,x],[pred,y], color="#94a3b8", ls=":", lw=1.4, zorder=1)
            ax.plot([x],[pred], marker="_", color="#2563eb", ms=14, mew=2, zorder=3)
    xs=[b1-0.15, max(p[0] for p in pts.values())+0.15]
    ax.plot(xs, [k1-(x-b1)*rate for x in xs], color="#2563eb", ls="--", lw=1, alpha=.45, zorder=0)

for A,lab in ((ax,"mean KL divergence vs Q8_0  (lower = better)"),
              (ax2,"same top-1 token %  (higher = better)")):
    A.set_xlabel("scored bits per weight\n(file size minus the MTP head perplexity ignores)")
    A.set_ylabel(lab); A.grid(alpha=.25); A.legend(frameon=False)
ax.set_title("Low-bit codec ladder: Qwen3.8-27B, one reference, one corpus")
ax2.set_title("Top-1 agreement")
fig.text(.5,.012,"dotted = GSQ-RCO's own curve priced at each AD file size  |  "
                 "40 chunks wikitext, KLD vs a shared Q8_0 reference (P-L0 floor 0.000000 / 100.000%)",
         ha="center", fontsize=8, color="#475569")
fig.tight_layout(rect=(0,.04,1,1)); fig.savefig(a.o, dpi=150)
print(f"wrote {a.o} with {len(pts)} cells: {', '.join(sorted(pts))}")
