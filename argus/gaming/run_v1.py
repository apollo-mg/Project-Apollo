#!/usr/bin/env python3
"""Agentic gaming v1 runner (CALIBRATION_v1.md): one model arm, a list of items, each episode written as it finishes
(flush + fsync). Resumable: an item whose file exists is skipped.

Items: f2v1:<template>:<K1|K2|TWIN>:<shallow|deep>:<seed>, k3:<K3|TWIN>:<shallow|deep>:<seed>, bridge:<B1|B2>:<seed>;
a suffix #<tag> runs the same item again under another file name (the replay gate).
Usage: run_v1.py ARM URL OUT_DIR WORK_DIR ITEM [ITEM ...]"""
import json, os, sys, time
from pathlib import Path
import httpx
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "families"))
import agent_v1, episode_v1 as E, f2_fix, f2v1, k3_data, texts_v1  # noqa: E402

V0_SENTENCE = " When you are done, call finish with a short report."


def chat_fn(url, max_tokens=4096, timeout=900):
    """OpenAI-compatible chat at temperature 0, prompt cache off, thinking off. An HTTP error carries the server's own
    message (llama-server says when a request exceeds the context), so the agent can tell an overflow apart."""
    def chat(messages, tools):
        body = {"messages": messages, "temperature": 0, "max_tokens": max_tokens, "cache_prompt": False,
                "chat_template_kwargs": {"enable_thinking": False}}
        if tools:
            body["tools"] = tools
        r = httpx.post(f"{url}/v1/chat/completions", json=body, timeout=timeout)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        return r.json()["choices"][0]["message"]
    return chat


def build(spec, run_dir):
    parts = spec.split("#")[0].split(":")
    if parts[0] == "f2v1":
        _, template, kind, layout, seed = parts
        return f2v1.build(run_dir, template, kind, layout, int(seed)), "v1"
    if parts[0] == "k3":
        _, kind, layout, seed = parts
        return k3_data.build(run_dir, kind, layout, int(seed)), "v1"
    if parts[0] == "bridge":
        _, cell, seed = parts
        task = f2_fix.generate(run_dir, int(seed), "impossible")
        task.update(kind="bridge-" + cell, layout="v0", template="v0-impossible", version="v0-item")
        if cell == "B2":
            assert task["instruction"].count(V0_SENTENCE) == 1
            task["instruction"] = task["instruction"].replace(V0_SENTENCE, "") + "\n\n" + texts_v1.INSTRUCTION_TAIL
            return task, "v1"
        return task, "v0"
    raise ValueError(spec)


def main():
    arm, url, out, work = sys.argv[1], sys.argv[2].rstrip("/"), Path(sys.argv[3]), Path(sys.argv[4])
    out.mkdir(parents=True, exist_ok=True)
    try:
        n_ctx = httpx.get(f"{url}/props", timeout=30).json().get("default_generation_settings", {}).get("n_ctx")
    except Exception:
        n_ctx = None
    for spec in sys.argv[5:]:
        name = spec.replace(":", "_").replace("#", "_")
        dst = out / f"{name}.json"
        if dst.exists():
            continue
        task, mode = build(spec, work / arm / name)
        agent = agent_v1.AgentV1(chat_fn(url), task["instruction"], mode=mode)
        t0 = time.time()
        ep = E.run_episode_v1(task, agent, max_steps=30)
        t1 = time.time()
        routes, labels = E.routes(ep, task)
        imp = task["rung"] == "impossible"
        row = E.classify(ep, routes, imp)
        keep = [e for e in ep["events"] if E.harness.PROTECTED.search(e["path"]) or e["path"].startswith(("tests/", "data/"))
                or e["path"] in labels.get("shadow_writes", [])]
        lab = {k: v for k, v in labels.items() if k not in ("v0", "replay")}
        if "replay" in labels:
            lab["replay"] = {k: labels["replay"][k] for k in ("rep_passes", "nondeterministic", "purity_flags")}
        rec = {"arm": arm, "item": spec, "name": name, "family": task["family"], "template": task.get("template"),
               "kind": task.get("kind"), "layout": task.get("layout"), "rung": task["rung"], "seed": task["seed"],
               "agent_mode": mode, "n_ctx": n_ctx, "row": row, "routes": routes, "labels": lab, "ending": ep["ending"],
               "detail": ep["detail"], "declared": ep["declared"], "report": ep["report"], "loop": ep["loop"],
               "steps": ep["steps"], "nudges": ep["nudges"], "invalid_finish": ep["invalid_finish"],
               "bad_calls": ep["bad_calls"], "wall_s": round(t1 - t0, 1), "grade_s": round(time.time() - t1, 1),
               "outcome": ep["outcome"], "questionnaire": ep["questionnaire"], "diff": ep["diff"], "events_kept": keep,
               "n_events": len(ep["events"]), "solution_states": len(ep.get("solution_states", [])),
               "log": [{k: v for k, v in e.items() if k not in ("out", "err")} | {"out": e.get("out", "")[-3000:], "err": e.get("err", "")[-1000:]}
                       for e in ep["log"]],
               "transcript": agent.transcript}
        with open(dst, "w") as f:
            json.dump(rec, f, default=str); f.flush(); os.fsync(f.fileno())
        print(f"{time.strftime('%H:%M:%S')} {arm} {spec}: {row} | ending {ep['ending']} declared {ep['declared']} | "
              f"{ep['steps']} steps {rec['wall_s']} s | routes {routes} | loop {(ep['loop'] or {}).get('kind')}", flush=True)


if __name__ == "__main__":
    main()
