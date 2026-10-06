#!/usr/bin/env python3
"""One llama.cpp MTP chat call, written as a Juke external receipt.

Start the server yourself, then point this at it. One warmup is discarded.
The second call is the receipt. No width sweep, no KV sweep, no second drafter.

  llama-server -m TARGET --model-draft DRAFT \\
    --spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-p-min 0 \\
    --reasoning off -ngl 99 -c 262144 -fa on -np 1 --metrics --no-webui \\
    --host 127.0.0.1 --port 18081

  python3 tools/capture_gemma4_mtp_receipt.py \\
    --base http://127.0.0.1:18081 \\
    --prompt /path/to/prose.txt \\
    --target TARGET --draft DRAFT \\
    --argv "<the command above>" \\
    --out receipt.json

The prompt file bytes are the shared input. Hash them before sending the file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

COUNTERS = (
    "llamacpp:spec_decode_num_draft_tokens_total",
    "llamacpp:spec_decode_num_accepted_tokens_total",
    "llamacpp:spec_decode_num_drafts_total",
)


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def request_json(method: str, url: str, body: dict | None = None, timeout: int = 1200):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode()) if raw else {}


def request_text(url: str, timeout: int = 30) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode(errors="replace")


def metric_values(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        name, _, rest = line.partition("{")
        if rest:
            key = name + "{" + rest.split("}", 1)[0] + "}"
            value = rest.split("}", 1)[1].split()[0]
        else:
            parts = line.split()
            if len(parts) != 2:
                continue
            key, value = parts
        try:
            out[key] = float(value)
        except ValueError:
            continue
    return out


def wait_ready(base: str) -> None:
    import time

    deadline = time.time() + 900
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/health", timeout=5) as resp:
                if resp.status == 200:
                    return
        except urllib.error.HTTPError as exc:
            if exc.code not in (503, 404):
                raise
        except urllib.error.URLError:
            pass
        time.sleep(3)
    raise SystemExit("server did not reach /health 200")


def keep_settings(blob: dict) -> dict:
    kept = {}
    for key, value in blob.items():
        name = key.lower()
        if any(
            part in name
            for part in ("specul", "reason", "cache", "n_ctx", "chat_format", "temperature")
        ):
            kept[key] = value
    return kept


def template_mark(template: str) -> dict:
    return {
        "sha256": hashlib.sha256(template.encode()).hexdigest(),
        "chars": len(template),
        "has_channel": "<|channel>" in template or "<|channel|>" in template,
        "has_thought": "thought" in template,
        "has_enable_thinking": "enable_thinking" in template,
    }


def position_hits(before: dict[str, float], after: dict[str, float]) -> list[int]:
    hits = []
    index = 0
    while True:
        key = f'llamacpp:spec_decode_num_accepted_tokens_per_pos_total{{position="{index}"}}'
        if key not in after and key not in before:
            break
        hits.append(int(after.get(key, 0) - before.get(key, 0)))
        index += 1
    return hits


def chat(base: str, prompt: str) -> dict:
    return request_json(
        "POST",
        base + "/v1/chat/completions",
        {
            "model": "gemma",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
            "temperature": 0,
            "stream": False,
            "cache_prompt": False,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:18081")
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--argv", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    prompt_bytes = args.prompt.read_bytes()
    prompt_text = prompt_bytes.decode().strip()
    target_sha, target_bytes = sha256_file(args.target)
    draft_sha, draft_bytes = sha256_file(args.draft)
    wait_ready(args.base)
    props = request_json("GET", args.base + "/props")
    tokenized = request_json(
        "POST", args.base + "/tokenize", {"content": prompt_text, "add_special": False}
    )
    rendered = request_json(
        "POST",
        args.base + "/apply-template",
        {"messages": [{"role": "user", "content": prompt_text}]},
    )
    rendered_prompt = rendered.get("prompt") or ""
    rendered_tokens = request_json(
        "POST",
        args.base + "/tokenize",
        {"content": rendered_prompt, "add_special": False},
    )
    chat(args.base, prompt_text)
    try:
        metrics_before = metric_values(request_text(args.base + "/metrics"))
    except urllib.error.HTTPError:
        metrics_before = {}
    measured = chat(args.base, prompt_text)
    try:
        metrics_after = metric_values(request_text(args.base + "/metrics"))
    except urllib.error.HTTPError:
        metrics_after = {}

    usage = measured.get("usage") or {}
    timings = measured.get("timings") or {}
    choice = (measured.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content") or ""
    settings = measured.get("generation_settings") or props.get("default_generation_settings") or {}
    if not isinstance(settings, dict):
        settings = {}
    hits = position_hits(metrics_before, metrics_after)
    draft_n = int(timings.get("draft_n") or 0)
    draft_acc = int(timings.get("draft_n_accepted") or 0)
    predicted_n = int(usage.get("completion_tokens") or timings.get("predicted_n") or 0)
    predicted_ms = float(timings.get("predicted_ms") or 0)
    metric_rounds = int(metrics_after.get(COUNTERS[2], 0) - metrics_before.get(COUNTERS[2], 0))
    # One verified token per pass, plus the drafts that pass accepted.
    rounds = metric_rounds or max(predicted_n - draft_acc, 0)
    ids = choice.get("tokens") if isinstance(choice.get("tokens"), list) else measured.get("tokens")
    if not isinstance(ids, list):
        ids = []
    raw_ids = tokenized.get("tokens") or []
    rendered_ids = rendered_tokens.get("tokens") or []
    template = props.get("chat_template") or ""
    reasoning_text = message.get("reasoning_content") or ""

    receipt = {
        "schema": "juke.gemma4-external-receipt.v1",
        "scope": (
            "Not a Juke replay. Not a scored published_bar. butter_execution stays "
            "not-run and token_ids stays empty. One llama.cpp MTP chat call."
        ),
        "date": date.today().isoformat(),
        "engine": {
            "name": "llama.cpp",
            "argv": args.argv,
            "props_build": props.get("build_info") or props.get("build"),
            "model_path": props.get("model_path"),
            "total_slots": props.get("total_slots"),
            "modalities": props.get("modalities"),
            "chat_template_caps": props.get("chat_template_caps"),
            "chat_template": template_mark(template) if isinstance(template, str) else None,
        },
        "host": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "machine": platform.machine(),
        },
        "files": {
            "target": str(args.target),
            "target_bytes": target_bytes,
            "target_sha256": target_sha,
            "draft": str(args.draft),
            "draft_bytes": draft_bytes,
            "draft_sha256": draft_sha,
            "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        },
        "request": {
            "endpoint": "/v1/chat/completions",
            "temperature": 0,
            "max_tokens": 256,
            "cache_prompt": False,
            "spec_draft_n_max": 2,
            "reasoning": "off on the server command",
        },
        "prompt_token_ids": raw_ids,
        "prompt_tokens_from_tokenize": len(raw_ids),
        "rendered_prompt_sha256": hashlib.sha256(rendered_prompt.encode()).hexdigest(),
        "rendered_prompt_token_ids": rendered_ids,
        "rendered_prompt_tokens": len(rendered_ids),
        "rendered_prompt_prefix": rendered_prompt[:160],
        "tokens_evaluated": usage.get("prompt_tokens"),
        "generated_token_ids": ids,
        "generated_token_ids_note": (
            "Empty when the server does not return ids. Do not invent them from the text."
        ),
        "content_prefix": content[:160],
        "reasoning_content_chars": len(reasoning_text),
        "reasoning_content_prefix": reasoning_text[:160],
        "finish_reason": choice.get("finish_reason"),
        "server_settings": keep_settings(settings),
        "timings": timings,
        "measured": {
            "prompt_n": usage.get("prompt_tokens"),
            "prompt_ms": timings.get("prompt_ms"),
            "prompt_per_second": timings.get("prompt_per_second"),
            "predicted_n": predicted_n,
            "predicted_ms": predicted_ms,
            "predicted_per_second": timings.get("predicted_per_second"),
            "draft_n": draft_n,
            "draft_n_accepted": draft_acc,
            "accept_rate": round(draft_acc / draft_n, 4) if draft_n else None,
            "rounds": rounds,
            "rounds_from_metrics": metric_rounds,
            "position_hits": hits,
            "tok_per_pass": round(predicted_n / rounds, 2) if rounds else None,
            "pass_ms": round(predicted_ms / rounds, 2) if rounds else None,
            "template_extra_tokens": (
                None
                if usage.get("prompt_tokens") is None
                else int(usage["prompt_tokens"]) - len(raw_ids)
            ),
        },
    }
    args.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        f"wrote {args.out} predicted_per_second={timings.get('predicted_per_second')} "
        f"draft {draft_acc}/{draft_n} prompt_tokens={usage.get('prompt_tokens')}"
    )


if __name__ == "__main__":
    main()

