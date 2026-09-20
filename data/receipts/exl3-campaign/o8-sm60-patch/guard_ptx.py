import re, sys, os

# Mnemonics that ptxas rejects below sm_80. Every occurrence lives in an inference kernel
# (proved: all quantizer targets compiled clean in round 2, so none of these are emitted there).
TARGETS = ("mma.sync", "ldmatrix", "cp.async", ".acquire", ".acq_rel", ".relaxed", ".release")

GUARD_OPEN  = "#if defined(__CUDA_ARCH__) && (__CUDA_ARCH__ >= 800)\n"
GUARD_ELSE  = "#else\n    __trap();   // sm_60 stub: inference-only path, never reached by the converter\n"
GUARD_CLOSE = "#endif\n"

def find_asm_statements(src):
    """Yield (start, end) spans of complete `asm ... ;` statements."""
    spans = []
    for m in re.finditer(r'\basm\b\s*(volatile\s*)?\(', src):
        i = m.end() - 1          # at '('
        depth, j, instr = 0, i, False
        while j < len(src):
            ch = src[j]
            if ch == '"':        # skip string literal
                j += 1
                while j < len(src) and not (src[j] == '"' and src[j-1] != '\\'):
                    j += 1
            elif ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    k = j + 1
                    while k < len(src) and src[k] in ' \t\n':
                        k += 1
                    if k < len(src) and src[k] == ';':
                        spans.append((m.start(), k + 1))
                    break
            j += 1
    return spans

def patch(path):
    src = open(path).read()
    spans = find_asm_statements(src)
    hits = [(s, e) for (s, e) in spans if any(t in src[s:e] for t in TARGETS)]
    if not hits:
        return 0
    out, prev = [], 0
    for (s, e) in hits:
        line_start = src.rfind("\n", 0, s) + 1
        indent = src[line_start:s]
        if indent.strip():                 # not at start of line; bail on this one
            continue
        out.append(src[prev:line_start])
        out.append(GUARD_OPEN)
        out.append(src[line_start:e])
        out.append("\n")
        out.append(GUARD_ELSE)
        out.append(GUARD_CLOSE)
        prev = e
        while prev < len(src) and src[prev] == "\n":
            prev += 1
        out.append("\n")
    out.append(src[prev:])
    open(path, "w").write("".join(out))
    return len(hits)

total = 0
for p in sys.argv[1:]:
    n = patch(p)
    print(f"  {os.path.basename(p):32s} guarded {n} asm statements")
    total += n
print(f"TOTAL: {total}")
