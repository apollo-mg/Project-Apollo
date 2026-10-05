#!/usr/bin/env python3
"""Build a LocalMaxxing verified-run payload from one lmx run + the g4_proxy.py capture of the SAME requests.
The evidence (prompt, output, llama.cpp timings, draft counts) comes from the lmx run's median timed request
(captures[0] is lmx's untimed warmup; ties take the first). Writes runs/sub_<ARM>.json (lmx run + patch) via
`lmx speed-test runs edit`; never submits.
usage: build_submission.py ARM CANONICAL_PROMPT_FILE SPEC_N "<commandSnippet>" "<notes>" [ENGINE_COMMIT]"""
import hashlib, json, shutil, statistics, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def main(arm, canon_file, spec_n, command, notes, commit="50569eb87"):
    spec_n = int(spec_n)
    lm = json.loads((RUNS / f"lmx_{arm}.json").read_text())
    caps = [json.loads(l) for l in open(RUNS / f"capture_{arm}.jsonl")]
    canon = Path(canon_file).read_text()
    samples = [s["tokSOut"] for s in lm["samples"]]
    med = statistics.median(samples); i = samples.index(med)
    if len(caps) != len(samples) + 1:
        sys.exit(f"capture count {len(caps)} != timed {len(samples)} + 1 warmup")
    r = caps[1 + i]
    req = r["request"]["messages"][-1]["content"]
    nonce_line, rest = req.split("\n", 1)
    if not nonce_line.startswith("[LocalMaxxing cache-bust nonce:") or rest != canon:
        sys.exit("request prompt is not nonce + canonical text")
    text, t = r["text"], r["timings"]
    if not text:
        sys.exit("empty content (thinking mode?)")
    patch = {"contextLength": 262144, "notes": notes,
             "engineRepository": "https://github.com/ggml-org/llama.cpp", "engineCommit": commit,
             "engineVersion": f"b-{commit}", "engineBuild": "HIP gfx1201, ROCm 7.2",
             "promptSha256": hashlib.sha256(canon.encode()).hexdigest(), "promptSample": req[:2000],
             "outputSha256": hashlib.sha256(text.encode()).hexdigest(),
             "outputSample": text if len(text) <= 4000 else text[:3000] + " … " + text[-1000:],
             "engineTimingsRaw": {"llamacpp_timings": t, "usage": r["usage"], "finishReason": r["finish_reason"],
                                  "clientTiming": {"rep": f"timed request {i + 1} of {len(samples)} (median)",
                                                   "tokSOut": med, "ttftMs": lm["samples"][i].get("ttftMs")}},
             "engineFlags": {"commandSnippet": command, "temperature": 0}}
    if spec_n and t.get("draft_n"):
        dn, da = t["draft_n"], t["draft_n_accepted"]
        patch["engineFlags"].update({"specDraftTokens": dn, "specAcceptedTokens": da,
                                     "specAcceptanceRate": round(da / dn, 6),
                                     "specMeanAcceptedLength": round(1 + da / (dn / spec_n), 6)})
    assert len(json.dumps(patch["engineTimingsRaw"])) <= 8192
    out = RUNS / f"sub_{arm}.json"
    shutil.copy(RUNS / f"lmx_{arm}.json", out)
    subprocess.run(["lmx", "speed-test", "runs", "edit", str(out), "--set-json", json.dumps(patch)], check=True,
                   stdout=subprocess.DEVNULL)
    print(f"{out}: median {med} (timed request {i + 1}), spec {patch['engineFlags'].get('specDraftTokens')}/"
          f"{patch['engineFlags'].get('specAcceptedTokens')}, output {len(text)} chars")


if __name__ == "__main__":
    main(*sys.argv[1:])
