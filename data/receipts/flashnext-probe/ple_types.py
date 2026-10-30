# GGUF header reader: type and size of the n-gram table and the main tensor families. Usage: ple_types.py FILE... (shards of one model)
import sys, collections
from gguf import GGUFReader
tot = collections.Counter(); ple = {}
for f in sys.argv[1:]:
    for t in GGUFReader(f, "r").tensors:
        if t.name in ("per_layer_token_embd.weight", "token_embd.weight", "output.weight"): ple[t.name] = (t.tensor_type.name, round(int(t.n_bytes) / 1e9, 2), [int(x) for x in t.shape])
        tot[t.tensor_type.name] += int(t.n_bytes)
print(sys.argv[1].split("/")[-1]); print("  ", ple); print("  ", {k: round(v / 1e9, 1) for k, v in tot.most_common(6)})
