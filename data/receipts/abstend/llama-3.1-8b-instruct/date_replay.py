"""PREREG_DRIFT_CAUSE.md Addendum 1: is the date in Llama 3.1's system prompt the "system update" effect? The 30 items of
replay_abench.py: render with /apply-template, replace the date, send to /completion with the same seed and sampling.
Prints only equality flags, never item or answer text."""
import json, re, sys, urllib.request, zlib
AB = "/mnt/TG_2TB/Projects/Apollo/data/receipts/abstentionbench/raw/"; ITEMS = "/mnt/TG_2TB/toolchains/AbstentionBench/sub1000_items.jsonl"
H = "http://127.0.0.1:8197"; OUT = sys.argv[1]; DATE = re.compile(r"Today Date: \d\d \w{3} \d{4}")
L = lambda f: {(r["dataset"], str(r["index"])): r for r in map(json.loads, open(AB + f)) if "error" not in r}
A, B = L("LLAMA8.jsonl"), L("L31AB.jsonl")
items = {(d["dataset"], str(d["index"])): d for d in map(json.loads, open(ITEMS))}
diff = [k for k in sorted(B) if A[k]["content"] != B[k]["content"]][:20]; same = [k for k in sorted(B) if A[k]["content"] == B[k]["content"]][:10]


def post(path, body):
    rq = urllib.request.Request(H + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(rq, timeout=1800).read())


seed = lambda k: (123456789 + zlib.crc32(f"{k[0]}:{k[1]}".encode())) % (2**31)
SAMPLE = {"temperature": 0.8, "top_p": 0.95, "cache_prompt": False}


def chat(k):
    b = {"messages": [{"role": "user", "content": items[k]["question"]}], "max_tokens": 4000, "seed": seed(k), **SAMPLE}
    return post("/v1/chat/completions", b)["choices"][0]["message"].get("content") or ""


def raw(k, prompt):
    return post("/completion", {"prompt": prompt, "n_predict": 4000, "seed": seed(k), **SAMPLE})["content"]


rows = []
for k in diff + same:
    p = post("/apply-template", {"messages": [{"role": "user", "content": items[k]["question"]}]})["prompt"]; assert len(DATE.findall(p)) == 1
    with_date = lambda d: DATE.sub("Today Date: " + d, p)
    n = {"key": k, "group": "diverged" if k in diff else "identical", "today_raw_eq_chat": raw(k, p) == chat(k), "d28_eq_L31AB": raw(k, with_date("28 Oct 2026")) == B[k]["content"]}
    if k in diff:
        n["d23_eq_LLAMA8"] = raw(k, with_date("23 Oct 2026")) == A[k]["content"]; n["d24_eq_LLAMA8"] = raw(k, with_date("24 Oct 2026")) == A[k]["content"]
    rows.append(n); json.dump({"today": DATE.search(p).group(0), "rows": rows}, open(OUT, "w"), indent=1)
    print(k[0][:12], k[1], {f: v for f, v in n.items() if f not in ("key", "group")}, flush=True)
for g in ("diverged", "identical"):
    R = [r for r in rows if r["group"] == g]
    print(g, len(R), {f: sum(r.get(f, False) for r in R) for f in ("today_raw_eq_chat", "d28_eq_L31AB", "d23_eq_LLAMA8", "d24_eq_LLAMA8")},
          "either LLAMA8 date:", sum(r.get("d23_eq_LLAMA8", False) or r.get("d24_eq_LLAMA8", False) for r in R))
