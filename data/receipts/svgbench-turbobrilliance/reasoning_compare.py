#!/usr/bin/env python3
"""Does the mode change the reasoning, the answer, or neither? Counts over the saved traces (reps 2-5;
rep 1 kept counts only, see Deviation 1). Run from this directory.

Per trace: reasoning chars, whether the reasoning names the persona or the system prompt, OMNI's five
required DIMENSION headings, CODER's listed vocabulary, self-revisions per 1k chars, and the answer's prose
outside the SVG. A capped rep's answer is cut mid-fence, so its prose count includes SVG text."""
import glob, json, os, re

ARMS = ["CTRL", "CODER", "QUINN", "OMNI"]
# Words the reasoning would use to talk ABOUT the injected block (persona named, or the instruction itself).
META = re.compile(r"harley|quinn|persona|in character|devoracle|system prompt|my framework|diagnostic framework|"
                  r"dimension", re.I)
DIM = re.compile(r"DIMENSION\s*([1-5])", re.I)
# CODER block, "Talks like": its listed vocabulary.
CODER_VOCAB = ["latency", "throughput", "coupling", "abstraction", "deterministic", "backpressure",
               "zero-allocation", "monotonic"]
# Self-revision markers; reported per 1,000 reasoning chars because raw counts track length.
REV = re.compile(r"\b(actually|wait|hmm|let me (?:re|adjust|fix|reconsider|redo|recalculate))", re.I)


def prose(content):
    """Answer text with fenced blocks and the SVG removed."""
    t = re.sub(r"```.*?```", " ", content, flags=re.S)
    t = re.sub(r"<svg.*?</svg>", " ", t, flags=re.S | re.I)
    return re.sub(r"\s+", " ", t).strip()


rows = []
for arm in ARMS:
    for k in range(2, 6):
        base = f"{arm}_r{k}_p1"
        rpath = f"{base}.reasoning.txt"
        cpath = f"{base}.content.txt"
        partial = False
        if not os.path.exists(rpath):
            rpath, cpath, partial = f"{base}.partial_reasoning.txt", f"{base}.partial_content.txt", True
        if not os.path.exists(rpath):
            continue
        r = open(rpath).read()
        c = open(cpath).read() if os.path.exists(cpath) else ""
        p = prose(c)
        low_r, low_p = r.lower(), p.lower()
        rows.append({
            "arm": arm, "rep": k, "partial": partial,
            "reasoning_chars": len(r),
            "opening": re.sub(r"\s+", " ", r[:90]),
            "reasoning_names_block": len(META.findall(r)),
            "dimension_headings_reasoning": sorted(set(DIM.findall(r))),
            "dimension_headings_answer": sorted(set(DIM.findall(c))),
            "coder_vocab_reasoning": sum(low_r.count(w) for w in CODER_VOCAB),
            "coder_vocab_answer": sum(low_p.count(w) for w in CODER_VOCAB),
            "revisions_per_1k": round(1000 * len(REV.findall(r)) / max(1, len(r)), 2),
            "answer_prose_chars": len(p),
            "answer_prose_head": p[:160],
        })

json.dump(rows, open("reasoning_compare.json", "w"), indent=1)
hdr = ("arm", "rep", "r_chars", "names_block", "dims_r", "dims_a", "vocab_r", "vocab_a", "rev/1k", "prose")
print("\t".join(hdr))
for x in rows:
    print("\t".join(str(v) for v in (
        x["arm"], f'{x["rep"]}{"*" if x["partial"] else ""}', x["reasoning_chars"], x["reasoning_names_block"],
        "".join(x["dimension_headings_reasoning"]) or "-", "".join(x["dimension_headings_answer"]) or "-",
        x["coder_vocab_reasoning"], x["coder_vocab_answer"], x["revisions_per_1k"], x["answer_prose_chars"])))
print("* = capped at 480 s, partial text")
