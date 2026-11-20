"""Thinking mode for the agentic gaming runner (2026-11-19): off by default and byte-identical to the frozen v1
requests; on, the effort is passed explicitly and each reply's reasoning goes back into the history."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "argus" / "gaming"))
import agent_v1, run_v1  # noqa: E402

CALL = {"id": "c1", "type": "function", "function": {"name": "list_dir", "arguments": json.dumps({"path": "."})}}


def fake_chat(messages, tools):
    return {"role": "assistant", "content": "", "reasoning_content": "SENTINEL thoughts", "tool_calls": [CALL]}


def test_reasoning_kept_only_when_asked():
    for keep in (False, True):
        a = agent_v1.AgentV1(fake_chat, "do the task", keep_reasoning=keep)
        act = a.next_action([])
        assert act["tool"] == "list_dir"
        last = a.messages[-1]
        assert last["role"] == "assistant" and last["tool_calls"] == [CALL]
        assert ("reasoning_content" in last) is keep


def test_request_body_off_and_on(monkeypatch):
    seen = []

    class R:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "x"}, "finish_reason": "stop"}], "usage": {}}

    monkeypatch.setattr(run_v1.httpx, "post", lambda url, json, timeout: seen.append(json) or R())
    run_v1.chat_fn("http://h")([{"role": "user", "content": "q"}], None)
    run_v1.chat_fn("http://h", 16384, 3600, "xhigh")([{"role": "user", "content": "q"}], None)
    off, on = seen
    assert off == {"messages": [{"role": "user", "content": "q"}], "temperature": 0, "max_tokens": 4096,
                   "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
    assert on["chat_template_kwargs"] == {"enable_thinking": True, "reasoning_effort": "xhigh"} and on["max_tokens"] == 16384


def _probe():
    import importlib.util
    p = Path(__file__).resolve().parents[1] / "data" / "receipts" / "pi-thinking" / "probe_preserve.py"
    spec = importlib.util.spec_from_file_location("probe_preserve", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_probe_deciding_steps_and_strip():
    pp = _probe()
    T = pp.T
    fin = {"id": "f", "type": "function", "function": {"name": "finish", "arguments": json.dumps({"outcome": "impossible", "report": "r"})}}
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"},
            {"role": "assistant", "content": "", "reasoning_content": "r1", "tool_calls": [CALL]},
            {"role": "tool", "tool_call_id": "c1", "content": "out\n\n" + T.REMINDER},
            {"role": "assistant", "content": "", "reasoning_content": "r2", "tool_calls": [CALL]},
            {"role": "tool", "tool_call_id": "c1", "content": "out"},
            {"role": "assistant", "content": "", "reasoning_content": "r3", "tool_calls": [fin]},
            {"role": "tool", "tool_call_id": "f", "content": "finished"}]
    assert pp.deciding(msgs) == [("after_reminder", 4), ("finish", 6)]
    assert pp.action(msgs[6]) == "finish:impossible" and pp.action(msgs[4]) == "list_dir"
    s = pp.strip(msgs[:6])
    assert all("reasoning_content" not in m for m in s) and [m["content"] for m in s] == [m["content"] for m in msgs[:6]]
    msgs[4] = msgs[6]                       # the reply after the reminder IS the finish: probed once
    assert pp.deciding(msgs[:6]) == [("after_reminder", 4)]
