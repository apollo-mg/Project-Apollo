# Note — why `reasoning_budget_message` cannot interrupt a thought, and the ~10-line change that would let it

**2026-09-12. Source analysis only; nothing built, nothing measured.** Read against
`buun-llama-cpp` at `3823c9eb6`. Answers the question Mark put to buun: *"Do you know of any way to
inject a message to llama-server while the think blocks are still open?"*

**Short answer: no, not with the fields that exist — and the reason is one line of code, not a design
limitation.**

## What `reasoning_budget_message` actually does

`tools/server/server-schema.cpp:415-428`. The field's own description is the whole story — *"Message
to **prepend to the reasoning budget end tag** when forcing it"*:

```cpp
llama_tokens end_tag = ctx.params.sampling.reasoning_budget_end.front();
std::string message = json_value(data, "reasoning_budget_message", std::string());
if (!message.empty()) {
    llama_tokens message_tokens = common_tokenize(ctx.vocab, message, false, true);
    end_tag.insert(end_tag.begin(), message_tokens.begin(), message_tokens.end());
}
ctx.params.sampling.reasoning_budget_forced = std::move(end_tag);
```

The message and the closing tag become **one atomic forced sequence**. The sampler
(`common/reasoning-budget.cpp`) then runs this state machine:

```
COUNTING --(remaining hits 0)--> FORCING --(force_pos == forced_tokens.size())--> DONE
                                                                                  |
                                      re-arms ONLY if the model emits a new start tag
```

`FORCING` masks every logit except the next forced token (`:166-186`), so the model is made to emit
the message and then `</think>`. At `:139-143` the completed sequence transitions straight to `DONE`.

**So the close is structural.** This is the mechanism behind the empirical finding in
`RESULT_OVERTHINK_INJECTION_Q6K.md` — the message is the final content of the reasoning stream in
**38 of 38** delivered cells across two runs, with zero model text after it. It was never going to be
otherwise.

## Why there is no workaround from the API

Three escapes were checked and all three are closed:

- **Omit the end tag.** `reasoning_budget_forced` is *built from* `end_tag`; with no end tags the
  sampler is never constructed at all (`common/sampling.cpp:345` requires
  `!reasoning_budget_end.empty()`).
- **Make the first end tag harmless**, e.g. `reasoning_budget_end_tags: ["\n", "</think>"]` so
  `front()` is a newline. This fails because the same vector is the *detector* — any listed sequence
  ends the reasoning block — so a `"\n"` entry terminates thinking on the model's first newline.
- **Empty first tag.** Skipped by the loader: `if (!tag.empty())` at `:403`.

The `DONE` state does re-arm on a new start tag (`:146-161`, *"some models emit multiple `<think>`
blocks per response"*), so a model that spontaneously reopens `<think>` gets a fresh budget. But the
Qwen3.8 template gives it no reason to: after `</think>` the next thing it owes is the answer.

## The change that would make the experiment possible

A mode where the forced sequence is the message **only**, and completing it returns to `COUNTING`
instead of falling through to `DONE`. Roughly:

1. **Schema** — one field beside the existing three, e.g. `reasoning_budget_action: "close"`
   (current behaviour, default) or `"continue"`.
2. **`server-schema.cpp:415`** — under `"continue"`, set `reasoning_budget_forced = message_tokens`
   and do not prepend the end tag.
3. **`reasoning-budget.cpp:139`** — under `"continue"`, on forced-sequence completion set
   `state = COUNTING; remaining = budget; end_matcher.reset();` rather than `state = DONE`. The
   `end_match` bookkeeping at `:137,141` exists to report the end tag on `DONE` and is simply unused
   in this mode.

That is the whole feature: **the model is nudged mid-thought and keeps thinking, with the budget
re-armed.** It also composes with the existing `reasoning_control` flag, which already exists to
"end reasoning at runtime".

**One hazard worth naming up front:** with no end tag forced and the budget re-arming, a model that
never converges gets nudged forever. The mode needs a max-injection count (or a strictly decreasing
budget) or it is an infinite-generation bug rather than a feature. Better to ship that cap in the
first version than to discover it in someone's 32k context.

## What this is worth to the overthink-detector idea

It is the blocking dependency. As built, arm C is arm B with 495 extra characters appended after
deliberation has closed, which is why it changed **0 of 24 outcomes** at Q6_K and 2 of 24 at IQ3_M —
both times for the worse. The hypothesis *"a nudge mid-thought redirects a runaway search"* has not
been tested and cannot be tested through this API. With the change above it becomes a clean
experiment: same corpus, same cap, arms differing only in whether the nudge closes the thought or
interrupts it.

**Not verified:** whether upstream llama.cpp has since grown an equivalent hook, and whether anything
in the `reasoning_control` path already permits this from the server side. Both are worth a look
before proposing a patch.
