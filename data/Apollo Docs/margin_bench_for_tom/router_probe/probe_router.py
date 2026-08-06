#!/usr/bin/env python3
# Sequential routing-probe runner against an OpenAI-compatible endpoint.
# Greedy decode, exact-match on FINAL_ACTION / FINAL_TARGET / SOURCE_RANK.
import argparse, json, re, time, urllib.request

PAT = re.compile(
	r"FINAL_ACTION\s*=\s*([A-Za-z_]+)\s*;\s*FINAL_TARGET\s*=\s*([A-Za-z0-9_:/\.\-]+)\s*;\s*SOURCE_RANK\s*=\s*(\d+)")

def query(base_url, model, prompt, max_tokens, timeout):
	body = json.dumps({
		"model": model,
		"messages": [{"role": "user", "content": prompt}],
		"temperature": 0.0,
		"max_tokens": max_tokens,
		"logprobs": True,
		"top_logprobs": 4,
		"chat_template_kwargs": {"enable_thinking": False},
	}).encode()
	req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions",
		data=body, headers={"Content-Type": "application/json"})
	with urllib.request.urlopen(req, timeout=timeout) as resp:
		r = json.loads(resp.read())
	choice = r["choices"][0]
	usage = r.get("usage", {})
	lp = []
	for t in ((choice.get("logprobs") or {}).get("content") or []):
		runner_up = None
		for alt in t.get("top_logprobs", []):
			if alt["token"] != t["token"]:
				runner_up = alt["logprob"]
				break
		lp.append([t["token"], t["logprob"], runner_up])
	return choice["message"]["content"], usage.get("prompt_tokens"), usage.get("completion_tokens"), lp

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--base-url", default="http://127.0.0.1:8099/v1")
	ap.add_argument("--model", default="local")
	ap.add_argument("--data", required=True)
	ap.add_argument("--out", required=True)
	ap.add_argument("--max-tokens", type=int, default=64)
	ap.add_argument("--timeout", type=int, default=600)
	ap.add_argument("--label", default="")
	args = ap.parse_args()

	cases = [json.loads(l) for l in open(args.data, encoding="utf-8") if l.strip()]
	done = set()
	try:
		for l in open(args.out, encoding="utf-8"):
			if l.strip():
				done.add(json.loads(l)["id"])
	except FileNotFoundError:
		pass

	n_exact = n_err = 0
	f_action = f_target = f_rank = 0
	t0 = time.time()
	with open(args.out, "a", encoding="utf-8") as fo:
		for i, c in enumerate(cases, 1):
			if c["id"] in done:
				continue
			rec = {"id": c["id"], "label": args.label,
				"expected_action": c["expected_action"],
				"expected_target": c["expected_target"],
				"expected_rank": c["expected_rank"]}
			try:
				text, pt, ct, lp = query(args.base_url, args.model, c["user"],
					args.max_tokens, args.timeout)
				m = PAT.search(text or "")
				rec.update(raw=text, prompt_tokens=pt, completion_tokens=ct, lp=lp)
				if m:
					a, t, rk = m.group(1), m.group(2), int(m.group(3))
					rec.update(got_action=a, got_target=t, got_rank=rk,
						ok_action=(a == c["expected_action"]),
						ok_target=(t == c["expected_target"]),
						ok_rank=(rk == c["expected_rank"]))
					rec["exact"] = rec["ok_action"] and rec["ok_target"] and rec["ok_rank"]
				else:
					rec.update(exact=False, ok_action=False, ok_target=False,
						ok_rank=False, parse_fail=True)
			except Exception as e:
				rec.update(error=str(e), exact=False)
				n_err += 1
			fo.write(json.dumps(rec) + "\n")
			fo.flush()
			n_exact += bool(rec.get("exact"))
			f_action += bool(rec.get("ok_action"))
			f_target += bool(rec.get("ok_target"))
			f_rank += bool(rec.get("ok_rank"))
			if i % 10 == 0:
				print(f"  [{i}/{len(cases)}] exact={n_exact} "
					f"({time.time()-t0:.0f}s)", flush=True)

	n = len(cases) - len(done)
	if n:
		print(f"SUMMARY label={args.label} n={n} exact={n_exact}/{n} ({100*n_exact/n:.1f}%) "
			f"action={f_action}/{n} target={f_target}/{n} rank={f_rank}/{n} errors={n_err}")

if __name__ == "__main__":
	main()
