# sha256 of the n-gram table's raw bytes, read directly from the shard at its data offset; no inference. Usage: ple_hash.py SHARD...
import hashlib, sys
from gguf import GGUFReader
for f in sys.argv[1:]:
    for t in GGUFReader(f, "r").tensors:
        if t.name == "per_layer_token_embd.weight":
            h = hashlib.sha256(); left = int(t.n_bytes)
            with open(f, "rb") as fh:
                fh.seek(t.data_offset)
                while left:
                    b = fh.read(min(1 << 24, left)); h.update(b); left -= len(b)
            print(f.split("/")[-1], t.tensor_type.name, int(t.n_bytes), h.hexdigest())
