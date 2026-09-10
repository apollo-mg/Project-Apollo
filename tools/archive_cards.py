#!/usr/bin/env python3
"""Archive HuggingFace model cards for every model our receipts cite.

WHY: 16 receipt files cite card-specified sampling parameters ("card sampling temp 1.0 /
top_p 0.95 / top_k 20"). None of those cards were held locally. A card that is edited or
withdrawn makes the receipt unverifiable -- and cards get edited routinely, independent of
any platform ownership question. Two of this campaign's worst bugs (inherited min_p 0.05,
Ornith's coding-vs-general profile) were card-reading errors, so the card IS evidence.

Records provenance, not just content: the HF commit sha and lastModified let a reader check
this archive against the upstream page later, and the content sha256 detects silent edits
to our own copy.
"""
import hashlib, json, sys, time, urllib.request, urllib.error
from pathlib import Path

OUT = Path("/mnt/TG_2TB/Projects/Apollo/data/model_cards")
REPOS = [
    "unsloth/Qwen3.8-27B-GGUF", "bartowski/Qwen3.8-27B-GGUF", "Qwen/Qwen3.8-27B",
    "unsloth/Qwen3.6-27B-MTP-GGUF", "Qwen/Qwen3.6-35B-A3B", "bartowski/Qwen_Qwen3.6-35B-A3B-GGUF",
    "unsloth/DeepSeek-V4-Flash-0731-GGUF", "zai-org/GLM-4.7-Flash",
    "unsloth/Llama-3.2-3B-Instruct-GGUF", "meta-llama/Llama-3.2-3B-Instruct",
    "unsloth/Qwen3.5-9B-GGUF", "unsloth/Qwen3.5-4B-GGUF", "unsloth/Qwen3.5-9B-MTP-GGUF",
    "deepreinforce-ai/Ornith-1.0-35B", "unsloth/Kimi-K3-GGUF",
]
UA = {"User-Agent": "apollo-card-archiver/1.0"}

def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")

def main(extra):
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "MANIFEST.json"
    man = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    ok = miss = 0
    for repo in REPOS + extra:
        slug = repo.replace("/", "__")
        try:
            meta = json.loads(get(f"https://huggingface.co/api/models/{repo}"))
        except urllib.error.HTTPError as e:
            print(f"  MISS {repo}: HTTP {e.code}"); miss += 1; continue
        except Exception as e:
            print(f"  MISS {repo}: {type(e).__name__}"); miss += 1; continue
        try:
            card = get(f"https://huggingface.co/{repo}/raw/main/README.md")
        except Exception:
            card = ""                       # metadata is still worth keeping
        (OUT / f"{slug}.md").write_text(card)
        man[repo] = {
            "fetched": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "hf_sha": meta.get("sha"),               # pin: lets a reader diff against upstream
            "lastModified": meta.get("lastModified"),
            "license": (meta.get("cardData") or {}).get("license"),
            "base_model": (meta.get("cardData") or {}).get("base_model"),
            "gated": meta.get("gated", False),
            "downloads": meta.get("downloads"),
            "card_bytes": len(card),
            "card_sha256": hashlib.sha256(card.encode()).hexdigest()[:16],
        }
        lic = man[repo]["license"] or "?"
        print(f"  OK   {repo:44} {len(card):>7,}B  license={lic}  sha={str(meta.get('sha'))[:8]}")
        ok += 1
    manifest_path.write_text(json.dumps(man, indent=2, sort_keys=True))
    print(f"\n  archived {ok}, missed {miss} -> {OUT}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
