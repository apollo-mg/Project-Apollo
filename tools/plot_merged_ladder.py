#!/usr/bin/env python3
"""The merged fidelity curve: this ladder + the EXL3 campaign, one reference, one axis.

x = SCORED bits per weight (file minus the MTP head perplexity ignores). Campaign points are
converted from peak VRAM via VRAM_MiB = scored_MiB + 119.5, calibrated on the two arms measured
in both datasets (offsets 118.8 / 120.2 MiB). See FINDING_MERGED_CURVE.md.
"""
import json, argparse, math
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

MIB=1048576; N=27.21e9; OFF=119.5
NEW_MTP={"G-IQ2XS":348469248,"G-IQ3XXS":348469248,"C-XBIN":348469248,
         "A-IQ2XS":292067328,"A-IQ3XXS":292067328,"A-IQ3S":292067328,
         "B-PTQ1":0,"B-PQ2":0}
NEW_FAM={"G-IQ2XS":"GSQ-RCO","G-IQ3XXS":"GSQ-RCO","A-IQ2XS":"AD","A-IQ3XXS":"AD",
         "A-IQ3S":"AD","B-PTQ1":"Bonsai 2","B-PQ2":"Bonsai 2"}
CAMP=[("EXL3 2.50","EXL3",9116,0.0934,87.3),("UD-Q2_K_XL","unsloth",9404,0.0842,87.3),
      ("EXL3 3.00","EXL3",10568,0.0462,90.7),("UD-IQ3_XXS","unsloth",11532,0.0476,90.9),
      ("EXL3 3.50","EXL3",12016,0.0250,93.3),("i1-IQ3_M","i1",12240,0.0613,89.8),
      ("EXL3 4.00","EXL3",13468,0.0120,95.4),("UD-IQ4_XS","unsloth",13500,0.0157,94.2),
      ("UD-Q4_K_M","unsloth",15448,0.0078,96.2),("EXL3 5.00","EXL3",16372,0.0040,97.2),
      ("Q6_K","stock",21276,0.0028,97.7)]
STYLE={"EXL3":("#7c3aed","D"),"unsloth":("#0891b2","v"),"GSQ-RCO":("#2563eb","o"),
       "AD":("#dc2626","s"),"Bonsai 2":("#059669","^"),"i1":("#a16207","P"),"stock":("#475569","*")}

ap=argparse.ArgumentParser(); ap.add_argument("results",nargs="+"); ap.add_argument("-o",default="merged.png")
a=ap.parse_args()

pts=[]
for p in a.results:
    for line in open(p):
        line=line.strip()
        if not line: continue
        d=json.loads(line)
        if d.get("status")!="OK" or d["cell"] not in NEW_FAM: continue
        b=(int(d["bytes"])-NEW_MTP[d["cell"]])*8/N
        pts.append((d["cell"],NEW_FAM[d["cell"]],b,float(d["mean_kld"]),float(d["same_top"]),True))
for n,f,v,k,t in CAMP:
    pts.append((n,f,(v-OFF)*MIB*8/N,k,t,False))

fig,(ax,ax2)=plt.subplots(1,2,figsize=(14,6))
for fam,(col,mk) in STYLE.items():
    fp=sorted([p for p in pts if p[1]==fam],key=lambda p:p[2])
    if not fp: continue
    ax.plot([p[2] for p in fp],[p[3] for p in fp],marker=mk,color=col,label=fam,lw=1.8,ms=8,
            mfc=[("white" if not p[5] else col) for p in fp][0] if False else None)
    ax2.plot([p[2] for p in fp],[p[4] for p in fp],marker=mk,color=col,label=fam,lw=1.8,ms=8)
    for p in fp:
        ax.annotate(p[0],(p[2],p[3]),textcoords="offset points",xytext=(6,5),fontsize=7,color=col)

# lower envelope on KLD
env=[]; best=1e9
for p in sorted(pts,key=lambda p:p[2]):
    if p[3]<best: best=p[3]; env.append(p)
ax.plot([p[2] for p in env],[p[3] for p in env],color="#111827",ls="--",lw=1.2,alpha=.55,
        label="lower envelope",zorder=0)

ax.set_yscale("log")
ax.set_ylabel("mean KL divergence vs Q8_0  (log scale, lower = better)")
ax2.set_ylabel("same top-1 token %  (higher = better)")
for A in (ax,ax2):
    A.set_xlabel("scored bits per weight  (file size minus the MTP head perplexity ignores)")
    A.grid(alpha=.25,which="both"); A.legend(frameon=False,fontsize=8,ncol=2)
ax.set_title("Fidelity per byte across five codec families, one shared Q8_0 reference")
ax2.set_title("Top-1 agreement")
fig.text(.5,.012,"Qwen3.8-27B | wikitext-2, 40 chunks | buun-sm60-qual on 2x P100 | "
        "EXL3-campaign points converted from peak VRAM, calibrated on two arms measured in both sets",
        ha="center",fontsize=8,color="#475569")
fig.tight_layout(rect=(0,.04,1,1)); fig.savefig(a.o,dpi=150)
print(f"wrote {a.o}: {len(pts)} points, envelope = {', '.join(p[0] for p in env)}")
