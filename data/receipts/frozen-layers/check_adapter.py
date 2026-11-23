#!/usr/bin/env python3
"""PREREG_FROZEN_LAYERS check: the adapter GGUF holds LoRA tensors on exactly layers a..b, 14 per layer
(q/k/v/o/gate/up/down x lora_a/lora_b). Usage: check_adapter.py ADAPTER.gguf a-b   (exit 1 on mismatch)"""
import re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "engines" / "buun-llama-cpp" / "gguf-py"))
import gguf
path, spec = sys.argv[1], sys.argv[2]
a, b = map(int, spec.split("-")); want = set(range(a, b + 1))
names = [t.name for t in gguf.GGUFReader(path).tensors]
per = Counter(int(m.group(1)) for n in names if (m := re.match(r"blk\.(\d+)\.", n)))
other = [n for n in names if not n.startswith("blk.")]
ok = set(per) == want and all(v == 14 for v in per.values()) and not other
print(f"{Path(path).name}: {len(names)} tensors, layers {min(per)}-{max(per)} ({len(per)}), per layer {sorted(set(per.values()))}, "
      f"non-layer {len(other)}; expected {spec} x14 = {14 * len(want)} -> {'OK' if ok else 'MISMATCH'}")
sys.exit(0 if ok else 1)
