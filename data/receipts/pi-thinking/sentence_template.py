#!/usr/bin/env python3
"""The 'sentence alone' cell (PREREG_SENTENCE.md): the model's own chat template with ONE change, so that the xhigh
instruction sentence can be injected with thinking off, at exactly the place the template puts it with thinking on.

  patch  IN OUT        copy the served template (from /props) and add the switch `force_effort_instructions`
  capture URL OUT      on a server running the ORIGINAL template: save the reference renders
  check URL REF        on a server running the PATCHED template: the renders must equal the references
                       (1) thinking off, no switch: byte-identical to the original thinking-off render (the patch is inert);
                       (2) a multi-turn history with a tool call, thinking off: byte-identical to the original;
                       (3) thinking off + xhigh + the switch: the original xhigh thinking-ON render with only its
                           generation tail swapped for the thinking-off tail -- the sentence, nothing else.
Exit 0 only if every check holds."""
import json, sys, tempfile
from pathlib import Path
import httpx
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "argus" / "gaming")); sys.path.insert(0, str(ROOT / "argus" / "gaming" / "families"))
import k3_data, texts_v1 as T  # noqa: E402

TARGET = "{%- if enable_thinking is undefined or enable_thinking is true %}"
PATCHED = "{%- if enable_thinking is undefined or enable_thinking is true or force_effort_instructions is true %}"
SWITCH = {"enable_thinking": False, "reasoning_effort": "xhigh", "force_effort_instructions": True}
ON_TAIL, OFF_TAIL = "<think>\n", "<think>\n\n</think>\n\n"


def patch(src, dst):
    t = Path(src).read_text()
    assert t.count(TARGET) == 1, f"patch target found {t.count(TARGET)} times"
    Path(dst).write_text(t.replace(TARGET, PATCHED))


def _msgs():
    task = k3_data.build(Path(tempfile.mkdtemp()) / "t", "K3", "shallow", 2)
    first = [{"role": "system", "content": T.SYSTEM}, {"role": "user", "content": task["instruction"]}]
    call = {"id": "c1", "type": "function", "function": {"name": "list_dir", "arguments": json.dumps({"path": "."})}}
    hist = first + [{"role": "assistant", "content": "", "tool_calls": [call]},
                    {"role": "tool", "tool_call_id": "c1", "content": "exit code 0\nSPEC.md"}]
    return first, hist


def _render(url, messages, kw):
    r = httpx.post(f"{url}/apply-template", json={"messages": messages, "tools": T.V1["tools"], "chat_template_kwargs": kw},
                   timeout=120).json()
    return r.get("prompt", "")


def capture(url, out):
    first, hist = _msgs()
    ref = {"off": _render(url, first, {"enable_thinking": False}),
           "hist_off": _render(url, hist, {"enable_thinking": False}),
           "xhigh_on": _render(url, first, {"enable_thinking": True, "reasoning_effort": "xhigh"})}
    assert all(ref.values()) and ref["xhigh_on"].endswith(ON_TAIL) and ref["off"].endswith(OFF_TAIL)
    Path(out).write_text(json.dumps(ref, indent=1))
    print(f"captured references: {[len(v) for v in ref.values()]} chars")


def check(url, ref_file):
    ref = json.loads(Path(ref_file).read_text())
    first, hist = _msgs()
    want3 = ref["xhigh_on"][:-len(ON_TAIL)] + OFF_TAIL
    got = {"inert_first": _render(url, first, {"enable_thinking": False}),
           "inert_history": _render(url, hist, {"enable_thinking": False}),
           "sentence": _render(url, first, SWITCH)}
    res = {"inert_first": got["inert_first"] == ref["off"], "inert_history": got["inert_history"] == ref["hist_off"],
           "sentence_exact": got["sentence"] == want3,
           "sentence_present": "Reasoning effort is set to xhigh" in got["sentence"]}
    print(f"template check: {res}")
    return all(res.values())


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "patch":
        patch(sys.argv[2], sys.argv[3])
    elif cmd == "capture":
        capture(sys.argv[2], sys.argv[3])
    elif cmd == "check":
        sys.exit(0 if check(sys.argv[2], sys.argv[3]) else 1)
