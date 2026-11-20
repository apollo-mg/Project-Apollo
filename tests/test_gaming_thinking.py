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
