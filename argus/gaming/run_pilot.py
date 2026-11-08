#!/usr/bin/env python3
"""PILOT_v0.md runner: one model arm, 17 episodes, each written as it finishes (flush + fsync). Resumable: an episode
whose file exists is skipped. Usage: run_pilot.py ARM URL OUT_DIR WORK_DIR"""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "families"))
import f1_checksum, f2_fix, harness, mini_agent  # noqa: E402

PLAN = ([("F1", "easy", s, False) for s in (1, 2, 3)] + [("F1", "hard", s, False) for s in (1, 2, 3)]
        + [("F2", r, s, False) for r in ("easy", "hard", "impossible") for s in (1, 2, 3)]
        + [("F1", "easy", 1, True), ("F2", "easy", 1, True)])


def main():
    arm, url, out, work = sys.argv[1], sys.argv[2].rstrip("/"), Path(sys.argv[3]), Path(sys.argv[4])
    out.mkdir(parents=True, exist_ok=True)
    for fam, rung, seed, control in PLAN:
        name = f"{fam}_{rung}_s{seed}{'_control' if control else ''}"
        dst = out / f"{name}.json"
        if dst.exists():
            continue
        run_dir = work / arm / name
        task = (f1_checksum.generate(run_dir, seed, rung, with_key=not control) if fam == "F1"
                else f2_fix.generate(run_dir, seed, rung, control=control))
        agent = mini_agent.ModelAgent(mini_agent.http_chat(url, thinking=False, max_tokens=4096), task["instruction"])
        t0 = time.time()
        ep = harness.run_episode(task, agent, max_steps=30)
        labels = harness.DETECT[fam](ep)
        keep_events = [e for e in ep["events"] if e["inode"] == ep["key_ino"] or harness.PROTECTED.search(e["path"]) or e["path"].startswith("tests/")]
        rec = {"arm": arm, "name": name, "family": fam, "rung": rung, "seed": seed, "control": control,
               "wall_s": round(time.time() - t0, 1), "labels": labels, "outcome": ep["outcome"], "questionnaire": ep["questionnaire"],
               "report": ep["report"], "budget_exhausted": ep["budget_exhausted"], "agent_error": agent.error,
               "steps": len(ep["log"]), "diff": ep["diff"], "events_kept": keep_events, "n_events": len(ep["events"]),
               "log": [{k: v for k, v in e.items() if k not in ("out", "err")} | {"out": e.get("out", "")[-3000:], "err": e.get("err", "")[-1000:]} for e in ep["log"]],
               "transcript": agent.transcript}
        with open(dst, "w") as f:
            json.dump(rec, f, default=str); f.flush(); os.fsync(f.fileno())
        brief = {k: labels.get(k) for k in ("honest_solve", "s2_taken", "s1_tamper", "tamper", "s3_hardcode", "impossible_gamed", "honest_abstain", "false_impossibility")}
        print(f"{time.strftime('%H:%M:%S')} {arm} {name}: {rec['steps']} steps {rec['wall_s']} s err={agent.error} {brief}", flush=True)


if __name__ == "__main__":
    main()
