#!/usr/bin/env python3
"""Render one tool-call conversation through three chat templates and show whether the model's own
earlier tool call survives into the prompt: stock Qwen3.8-27B, DavidAU's Twin-Turbo as shipped, and
Twin-Turbo with a one-line fix to its {REASON:...} parser. Uses jinja2 (llama.cpp's minja can differ
in edge cases); the templates are read from the GGUF metadata, nothing else is loaded."""
import datetime, json, sys
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/gguf-py")
from gguf import GGUFReader
import jinja2

DAU = "/home/mark/Downloads/Qwen3.8-27B-TTURBO-Fable-C-Fusion-709-L-Uncen-NM-DAU-NEO-MTP-IQ3_M.gguf"
STOCK = "/mnt/TG_2TB/AI/Models/Qwen3.8-27B-UD-IQ2_M.gguf"
BROKEN = '{% set store.messages = store.messages + [{"role": msg.role, "content": txt}] %}'
FIXED = '{% set store.messages = store.messages + [msg] %}'   # keep untagged messages whole


def tmpl(path):
    f = GGUFReader(path).fields["tokenizer.chat_template"]
    return bytes(f.parts[f.data[0]]).decode()


def raise_exception(m):
    raise ValueError(m)


env = jinja2.Environment(extensions=["jinja2.ext.loopcontrols"])
env.globals.update(raise_exception=raise_exception, strftime_now=lambda f: datetime.datetime(2026, 9, 11).strftime(f))
env.filters["tojson"] = lambda v, **k: json.dumps(v, ensure_ascii=False)
tools = [{"type": "function", "function": {"name": "get_weather", "description": "Current weather for a city",
          "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}]
msgs = [{"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What's the weather in Paris?"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "type": "function",
          "function": {"name": "get_weather", "arguments": {"city": "Paris"}}}]},
        {"role": "tool", "content": "{\"temp_c\": 18}", "tool_call_id": "call_1", "name": "get_weather"},
        {"role": "user", "content": "And in Rome?"}]

dau = tmpl(DAU)
assert dau.count(BROKEN) == 1, "the rebuild line was not found exactly once"
for name, t in (("STOCK", tmpl(STOCK)), ("DAVIDAU as shipped", dau), ("DAVIDAU one-line fix", dau.replace(BROKEN, FIXED))):
    out = env.from_string(t).render(messages=msgs, tools=tools, add_generation_prompt=True, reasoning_effort="medium")
    turn = out.split("What's the weather in Paris?<|im_end|>\n", 1)[1].split("<|im_end|>", 1)[0]
    print(f"== {name}: earlier tool call kept = {'<tool_call>' in turn}")
    print("   assistant turn: " + turn.replace("\n", "\\n")[:200])
