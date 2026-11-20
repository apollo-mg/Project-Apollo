"""Tool-calling agent for the agentic gaming instrument v1 (DESIGN_v1.md section 4).

Differences from v0's mini_agent: one exit, finish(outcome, report), with outcome completed / impossible /
not_completed; a finish without a valid outcome gets the frozen feedback and costs a step; three replies in a row
without a tool call end the episode as "no tool call" and a request that fails after retries ends it as "model error"
(v0 turned both into a finish); malformed arguments and unknown tools get feedback and cost a step; the questionnaire
is re-asked once. mode="v0" swaps in v0's texts and finish(report) for the bridge cell; the endings stay v1's.
keep_reasoning=True (thinking runs, 2026-11-19) passes each reply's reasoning_content back in the history, as the Qwen3.8
template's preserve_thinking default expects; off (the default) leaves every thinking-off request byte-identical.
Actions returned to the episode runner: a tool call, {"tool": "_bad", "feedback": ...} or {"tool": "_end", ...}.
"""
import json
import texts_v1 as T


class AgentV1:
    def __init__(self, chat, instruction, mode="v1", max_output=3000, retries=2, keep_reasoning=False):
        self.chat, self.mode, self.max_output, self.retries = chat, mode, max_output, retries
        self.keep_reasoning = keep_reasoning
        self.texts = T.V1 if mode == "v1" else T.V0
        self.names = {t["function"]["name"] for t in self.texts["tools"]}
        self.messages = [{"role": "system", "content": self.texts["system"]}, {"role": "user", "content": instruction}]
        self.transcript, self._pending, self.nudges, self.error = [], None, 0, None
        self.last_usage, self.parse_failed = None, False

    def _assistant(self, msg, content, **extra):
        m = {"role": "assistant", "content": content, **extra}
        if self.keep_reasoning and msg and msg.get("reasoning_content"):
            m["reasoning_content"] = msg["reasoning_content"]
        return m

    def _ask(self, tools):
        last = None
        for _ in range(self.retries + 1):
            try:
                msg = self.chat(self.messages, tools)
                self.transcript.append(msg)
                self.last_usage = msg.get("_usage")
                return msg
            except Exception as e:                                   # server error, context overflow
                last = f"{type(e).__name__}: {str(e)[:200]}"
                if "Failed to parse tool call" in str(e):            # the server could not parse the model's call:
                    self.error, self.parse_failed = last, True       # a malformed call, not a dead server
                    return None
        self.error = last
        return None

    def _feed_back(self, history):
        if self._pending is None or not history:
            return
        h = history[-1]
        if h.get("feedback"):
            content = h["feedback"]
        else:
            out = h.get("out", "") + (("\n[stderr]\n" + h["err"]) if h.get("err") else "")
            if len(out) > self.max_output:                          # head and tail: errors and summaries sit at the end
                half = self.max_output // 2
                out = f"{out[:half]}\n[... {len(out) - 2 * half} characters pruned ...]\n{out[-half:]}"
            content = f"exit code {h.get('rc')}\n{out}"
        if h.get("reminder"):
            content += "\n\n" + h["reminder"]
        self.messages.append({"role": "tool", "tool_call_id": self._pending, "content": content})
        self._pending = None

    def next_action(self, history):
        self._feed_back(history)
        silent = 0
        while True:
            msg = self._ask(self.texts["tools"])
            if msg is None and self.parse_failed:                   # feedback and a step, as for any malformed call
                self.parse_failed = False
                self.messages.append({"role": "user", "content": "Your last tool call could not be parsed (its arguments "
                                      "were not valid JSON); nothing was run."})
                return {"tool": "_bad", "args": {"name": "?", "server_parse_error": True, "detail": self.error},
                        "feedback": None}
            if msg is None:                                         # context overflow is counted apart from other errors
                overflow = any(w in (self.error or "").lower() for w in ("context", "exceed", "too long", "n_ctx"))
                return {"tool": "_end", "args": {"ending": "context_overflow" if overflow else "model_error", "detail": self.error}}
            calls = msg.get("tool_calls") or []
            if calls:
                break
            silent += 1
            self.messages.append(self._assistant(msg, msg.get("content") or ""))
            if silent >= 3:
                return {"tool": "_end", "args": {"ending": "no_tool_call"}}
            self.nudges += 1
            self.messages.append({"role": "user", "content": self.texts["nudge"]})
        c = calls[0]
        self.messages.append(self._assistant(msg, msg.get("content") or "", tool_calls=[c]))
        self._pending = c.get("id") or "call_0"
        name, raw = c["function"]["name"], c["function"].get("arguments") or "{}"
        try:
            args = json.loads(raw) if isinstance(raw, str) else dict(raw)
            assert isinstance(args, dict)
        except (ValueError, AssertionError, TypeError):
            return {"tool": "_bad", "args": {"name": name, "raw": str(raw)[:500]},
                    "feedback": f"The arguments for {name} are not a valid JSON object; nothing was run."}
        if name not in self.names:
            return {"tool": "_bad", "args": {"name": name, **args},
                    "feedback": f"There is no tool called {name}. The tools are: {', '.join(sorted(self.names))}."}
        if name == "finish" and self.mode == "v1" and args.get("outcome") not in T.OUTCOMES:
            return {"tool": "_bad", "args": {"name": name, **args}, "feedback": T.FEEDBACK}
        if name == "finish":
            self.messages.append({"role": "tool", "tool_call_id": self._pending, "content": "finished"})
            self._pending = None
        return {"tool": name, "args": args}

    def questionnaire(self):
        if self.mode != "v1":
            return {}
        self.messages.append({"role": "user", "content": T.QUESTIONNAIRE})
        for attempt in (0, 1):
            msg = self._ask(None)
            if msg is None:
                return {**{k: None for k in T.Q_KEYS}, "_error": self.error}
            text = msg.get("content") or json.dumps(msg.get("tool_calls") or "")
            parsed = _parse(text)
            if parsed is not None:
                return {**parsed, "_asked": attempt + 1}
            self.messages.append(self._assistant(msg, text))
            if attempt == 0:
                self.messages.append({"role": "user", "content": T.REASK})
        return {**{k: None for k in T.Q_KEYS}, "_raw": text[:300], "_asked": 2}


def _parse(text):
    """The last JSON object in the reply that holds at least one of the questions, booleans only; else None."""
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for s in reversed(starts):
        e = text.rfind("}")
        while e > s:
            try:
                j = json.loads(text[s:e + 1])
            except ValueError:
                e = text.rfind("}", s, e)
                continue
            if isinstance(j, dict) and any(k in j for k in T.Q_KEYS):
                return {k: j[k] if isinstance(j.get(k), bool) else None for k in T.Q_KEYS}
            break
    return None
