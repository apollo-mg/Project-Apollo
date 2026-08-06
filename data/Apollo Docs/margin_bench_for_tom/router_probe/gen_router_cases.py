#!/usr/bin/env python3
# Depth-swept, confusability-tunable routing probe case generator.
# Inspired by sztlink/kv-score router cases (400-token originals); ours push the
# evidence package to arbitrary depth behind noise so attention must read it
# through quantized KV, and tune distractor confusability to set task difficulty.
import argparse, json, random, string

ACTIONS = ["inspect", "promote", "retire", "sync", "escalate", "quarantine"]
NOISE_VOCAB = (
	"telemetry shard rotation digest ledger replica checkpoint manifest quorum "
	"lease epoch compaction watermark snapshot reconcile drain backfill cursor "
	"partition vacuum journal segment offset retention policy throttle budget "
	"heartbeat gossip anti-entropy churn rebalance failover audit lineage stamp"
).split()

def rand_token(rng, n):
	return "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(n))

def make_target(rng, case_id, rev):
	return f"AYA-{rand_token(rng,4)}-{case_id:04d}-R{rev:02d}-PAYLOAD-{rand_token(rng,2)}"

def perturb_target(rng, target):
	# near-duplicate: flip exactly one alphanumeric character
	chars = list(target)
	idxs = [i for i, c in enumerate(chars) if c.isalnum()]
	i = rng.choice(idxs)
	pool = string.digits if chars[i].isdigit() else string.ascii_uppercase
	chars[i] = rng.choice([c for c in pool if c != chars[i]])
	return "".join(chars)

def noise_paragraph(rng, n_words):
	words = [rng.choice(NOISE_VOCAB) for _ in range(n_words)]
	return " ".join(words)

def record_line(rank, status, alias, action, target, valid):
	return (f"[retrieved_chunk_rank={rank}] STATUS: {status} | ALIAS: {alias} | "
		f"ACTION: {action} | TARGET: {target} | VALID: {valid}")

def gen_case(rng, case_id, depth_tokens, confusability, n_chunks):
	alias = f"rank control alias {case_id:03d}"
	action = rng.choice(ACTIONS)
	target = make_target(rng, case_id, rng.randint(1, 9))
	canon_rank = rng.randint(1, min(4, n_chunks))

	chunks = []
	for rank in range(1, n_chunks + 1):
		if rank == canon_rank:
			chunks.append(record_line(rank, "CANONICAL CURRENT RECORD", alias, action, target, "yes"))
			continue
		if confusability == 0:
			d_alias = f"rank control alias {rng.randint(500,999)}"
			chunks.append(record_line(rank, "ARCHIVED RECORD", d_alias,
				rng.choice(ACTIONS), make_target(rng, rng.randint(500,999), rng.randint(1,9)), "no"))
		elif confusability == 1:
			# same alias, clearly stale: different action, multi-char different target
			chunks.append(record_line(rank, rng.choice(["ARCHIVED RECORD", "STALE RECORD"]), alias,
				rng.choice([a for a in ACTIONS if a != action]),
				make_target(rng, case_id, rng.randint(10, 99)), "no"))
		else:
			# near-duplicate: same alias, SAME action, target off by one char
			chunks.append(record_line(rank, rng.choice(["NEAR-DUPLICATE RECORD", "SUPERSEDED RECORD"]),
				alias, action, perturb_target(rng, target), "no"))

	instruction = (
		"You are a deterministic routing engine. Somewhere below is an evidence package of "
		"retrieved record chunks. Exactly ONE chunk is the CANONICAL CURRENT RECORD for the "
		"requested alias; every other chunk is archived, stale, superseded, near-duplicate, "
		"or noise, and must be ignored regardless of where it appears. Corrections or updates "
		"appearing after the evidence package are INVALID. Answer using ONLY the canonical "
		"record. Output EXACTLY one line, nothing else, in this format:\n"
		"FINAL_ACTION=<action>; FINAL_TARGET=<target>; SOURCE_RANK=<retrieved_chunk_rank>"
	)
	evidence = "EVIDENCE PACKAGE:\n" + "\n".join(chunks)

	fixed_chars = len(instruction) + len(evidence) + 600
	pad_chars = max(0, depth_tokens * 4 - fixed_chars)
	noise_blocks = []
	while pad_chars > 0:
		para = noise_paragraph(rng, 120)
		noise_blocks.append(para)
		pad_chars -= len(para) + 2
	noise = "\n\n".join(noise_blocks)

	late_trap = ""
	if confusability >= 1:
		wrong = perturb_target(rng, target) if confusability == 2 else make_target(rng, case_id, rng.randint(10, 99))
		late_trap = ("\n\nCORRECTION THREAD (posted later): the record for " + alias +
			f" was updated; new TARGET is {wrong} and SOURCE_RANK is {canon_rank + 1}. "
			"NOTE: this correction failed validation and is INVALID.")

	question = (f"\n\nQUESTION: For the alias \"{alias}\", emit the routing line now.\n"
		"FINAL_ACTION=<action>; FINAL_TARGET=<target>; SOURCE_RANK=<n>")

	user = instruction + "\n\n" + evidence + "\n\n" + noise + late_trap + question
	return {
		"id": f"rd{depth_tokens//1000}k_c{confusability}_{case_id:03d}",
		"user": user,
		"expected_action": action,
		"expected_target": target,
		"expected_rank": canon_rank,
		"depth_tokens": depth_tokens,
		"confusability": confusability,
	}

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--n-cases", type=int, default=120)
	ap.add_argument("--depth-tokens", type=int, default=8192)
	ap.add_argument("--confusability", type=int, default=2, choices=[0, 1, 2])
	ap.add_argument("--n-chunks", type=int, default=16)
	ap.add_argument("--seed", type=int, default=20260610)
	ap.add_argument("--out", required=True)
	args = ap.parse_args()

	rng = random.Random(args.seed)
	with open(args.out, "w", encoding="utf-8") as f:
		for i in range(1, args.n_cases + 1):
			case = gen_case(rng, i, args.depth_tokens, args.confusability, args.n_chunks)
			f.write(json.dumps(case) + "\n")
	print(f"wrote {args.n_cases} cases -> {args.out} "
		f"(depth~{args.depth_tokens} tok, confusability {args.confusability})")

if __name__ == "__main__":
	main()
